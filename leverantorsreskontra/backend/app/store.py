"""The store: SQLite for structured data + the audit trail, filesystem for the
immutable originals and rendered page images (blobs don't belong in the DB).

Public surface used by the pipeline, intake worker and API:
  fingerprint / exists / save_original / save_page_image / page_image_path
  save_invoice(result)                 insert a freshly-read invoice (+ audit)
  get_result(id)                       reconstruct the full result dict
  list_results()                       the review queue
  verify_invoice(id, values, projects, actor)  apply corrections (+ audit)
  get_audit(id) / audit_integrity()    the trail and its tamper-check
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from decimal import Decimal

from . import bas, db, kontering, validation

MAX_HANDOVER_ATTEMPTS = 5

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# Serialises writes so the global audit hash chain stays consistent under the
# HTTP handlers and the intake worker running concurrently.
_write_lock = threading.Lock()


def _ensure() -> None:
    db.init()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---- filesystem: originals + page images ----

def _dir(invoice_id: str) -> Path:
    d = DATA_DIR / invoice_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def fingerprint(pdf_bytes: bytes) -> str:
    return hashlib.sha256(pdf_bytes).hexdigest()[:16]


def save_original(invoice_id: str, pdf_bytes: bytes) -> None:
    (_dir(invoice_id) / "original.pdf").write_bytes(pdf_bytes)


def save_page_image(invoice_id: str, page: int, image) -> None:
    image.save(_dir(invoice_id) / f"page_{page}.png", format="PNG")


def page_image_path(invoice_id: str, page: int) -> Path:
    return _dir(invoice_id) / f"page_{page}.png"


def original_pdf_path(invoice_id: str) -> Path:
    return _dir(invoice_id) / "original.pdf"


# ---- audit ----

def _append_audit(c, invoice_id, actor, action,
                  field_key=None, old_value=None, new_value=None, note=None) -> None:
    prev = c.execute("SELECT row_hash FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
    prev_hash = prev["row_hash"] if prev else ""
    ts = _now()
    payload = "|".join([
        prev_hash, invoice_id, ts, actor, action,
        field_key or "", old_value or "", new_value or "", note or "",
    ])
    row_hash = hashlib.sha256(payload.encode()).hexdigest()
    c.execute(
        "INSERT INTO audit(invoice_id, ts, actor, action, field_key, old_value, "
        "new_value, note, prev_hash, row_hash) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (invoice_id, ts, actor, action, field_key, old_value, new_value, note,
         prev_hash, row_hash),
    )


def get_audit(invoice_id: str) -> list[dict]:
    _ensure()
    with db.connect() as c:
        rows = c.execute(
            "SELECT seq, ts, actor, action, field_key, old_value, new_value, note "
            "FROM audit WHERE invoice_id=? ORDER BY seq", (invoice_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def audit_integrity() -> dict:
    """Recompute the global hash chain and report whether it is intact."""
    _ensure()
    with db.connect() as c:
        rows = c.execute(
            "SELECT invoice_id, ts, actor, action, field_key, old_value, new_value, "
            "note, prev_hash, row_hash FROM audit ORDER BY seq"
        ).fetchall()
    prev_hash = ""
    for i, r in enumerate(rows):
        payload = "|".join([
            prev_hash, r["invoice_id"], r["ts"], r["actor"], r["action"],
            r["field_key"] or "", r["old_value"] or "", r["new_value"] or "", r["note"] or "",
        ])
        expected = hashlib.sha256(payload.encode()).hexdigest()
        if r["prev_hash"] != prev_hash or r["row_hash"] != expected:
            return {"ok": False, "rows": len(rows), "broken_at": i + 1}
        prev_hash = r["row_hash"]
    return {"ok": True, "rows": len(rows), "broken_at": None}


# ---- invoices ----

def exists(invoice_id: str) -> bool:
    _ensure()
    with db.connect() as c:
        return c.execute("SELECT 1 FROM invoices WHERE id=?", (invoice_id,)).fetchone() is not None


def _summary(result: dict) -> tuple[str, str, str, int, str]:
    """Derive the denormalised queue columns: supplier, total, currency, issue
    count, and a lowercase blob for searching across the whole invoice."""
    by_key = {f["key"]: f["value"] for f in result["fields"]}
    supplier = by_key.get("supplier_name", "")
    total = by_key.get("total_amount", "")
    currency = by_key.get("currency", "")
    issues = sum(1 for s in result["signals"] if s.get("level") != "ok")
    parts = [result["filename"], *by_key.values(),
             *(li["description"] for li in result["line_items"])]
    search_text = " ".join(p for p in parts if p).lower()
    return supplier, total, currency, issues, search_text


def save_invoice(result: dict) -> None:
    """Persist a freshly-read invoice and record the ingest event."""
    _ensure()
    supplier, total, currency, issues, search_text = _summary(result)
    with _write_lock, db.connect() as c:
        if c.execute("SELECT 1 FROM invoices WHERE id=?", (result["id"],)).fetchone():
            return  # already stored (dedup)
        c.execute(
            "INSERT INTO invoices(id, filename, created_at, verified, pages_json, "
            "checks_json, signals_json, supplier, total, currency, issues, search_text) "
            "VALUES(?,?,?,0,?,?,?,?,?,?,?,?)",
            (result["id"], result["filename"], _now(),
             json.dumps(result["pages"]), json.dumps(result["checks"]),
             json.dumps(result["signals"]),
             supplier, total, currency, issues, search_text),
        )
        for f in result["fields"]:
            c.execute(
                "INSERT INTO fields(invoice_id, key, label, value, confidence, found, "
                "page, status, box_json) VALUES(?,?,?,?,?,?,?,?,?)",
                (result["id"], f["key"], f["label"], f["value"], f["confidence"],
                 int(f["found"]), f["page"], f["status"],
                 json.dumps(f["box"]) if f["box"] else None),
            )
        for it in result["line_items"]:
            c.execute(
                "INSERT INTO line_items(invoice_id, idx, description, quantity, "
                "unit_price, amount, confidence, page, status, box_json, project, "
                "konto, momskod) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (result["id"], it["index"], it["description"], it["quantity"],
                 it["unit_price"], it["amount"], it["confidence"], it["page"],
                 it["status"], json.dumps(it["box"]) if it["box"] else None,
                 it.get("project", ""), it.get("konto", ""), it.get("momskod", "")),
            )
        _append_audit(
            c, result["id"], "system", "ingested",
            note=f"{len(result['fields'])} fields, {len(result['line_items'])} line items",
        )


def get_result(invoice_id: str) -> dict | None:
    _ensure()
    with db.connect() as c:
        inv = c.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
        if inv is None:
            return None
        frows = c.execute(
            "SELECT * FROM fields WHERE invoice_id=? ORDER BY rowid", (invoice_id,)
        ).fetchall()
        lrows = c.execute(
            "SELECT * FROM line_items WHERE invoice_id=? ORDER BY idx", (invoice_id,)
        ).fetchall()

    fields = [
        {
            "key": r["key"], "label": r["label"], "value": r["value"],
            "confidence": r["confidence"], "found": bool(r["found"]),
            "page": r["page"], "status": r["status"],
            "box": json.loads(r["box_json"]) if r["box_json"] else None,
        }
        for r in frows
    ]
    line_items = [
        {
            "index": r["idx"], "description": r["description"], "quantity": r["quantity"],
            "unit_price": r["unit_price"], "amount": r["amount"],
            "confidence": r["confidence"], "page": r["page"], "status": r["status"],
            "box": json.loads(r["box_json"]) if r["box_json"] else None,
            "project": r["project"],
            "konto": r["konto"],
            "momskod": r["momskod"],
        }
        for r in lrows
    ]
    return {
        "id": inv["id"],
        "filename": inv["filename"],
        "verified": bool(inv["verified"]),
        "pages": json.loads(inv["pages_json"]),
        "fields": fields,
        "line_items": line_items,
        "checks": json.loads(inv["checks_json"]),
        "signals": json.loads(inv["signals_json"]),
        "verifikat": json.loads(inv["verifikat_json"]) if inv["verifikat_json"] else None,
        "attest_status": inv["attest_status"],
        "granskare": inv["granskare"],
        "granskad_at": inv["granskad_at"],
        "attestant": inv["attestant"],
        "attesterad_at": inv["attesterad_at"],
        "attest_kommentar": inv["attest_kommentar"],
    }


def query_invoices(q: str = "", status: str = "all",
                   page: int = 1, page_size: int = 15) -> dict:
    """The review queue: full-text-ish search + status filter + paging.

    Returns {items, total, page, page_size, pages}. `status` is all | todo | done.
    Search matches the per-invoice search_text (supplier, number, amounts, etc.).
    """
    _ensure()
    page = max(1, page)
    page_size = max(1, min(100, page_size))

    clauses, params = [], []
    q = (q or "").strip().lower()
    if q:
        clauses.append("search_text LIKE ?")
        params.append(f"%{q}%")
    if status == "todo":
        clauses.append("verified = 0")
    elif status == "done":
        clauses.append("verified = 1")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    with db.connect() as c:
        total = c.execute(f"SELECT COUNT(*) AS n FROM invoices {where}", params).fetchone()["n"]
        rows = c.execute(
            f"SELECT id, filename, supplier, total, currency, issues, verified, "
            f"handover_status FROM invoices {where} ORDER BY created_at DESC, filename "
            f"LIMIT ? OFFSET ?",
            [*params, page_size, (page - 1) * page_size],
        ).fetchall()

    items = [
        {
            "id": r["id"], "filename": r["filename"], "supplier": r["supplier"],
            "total": r["total"], "currency": r["currency"],
            "issues": r["issues"], "verified": bool(r["verified"]),
            "handover_status": r["handover_status"],
        }
        for r in rows
    ]
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
    }


def verify_invoice(invoice_id: str, field_values: dict[str, str],
                   projects: dict, actor: str,
                   codings: dict | None = None) -> dict | None:
    """Apply the reviewer's corrections and coding, recording each change
    (old -> new, by whom, when) in the audit trail. `codings` maps a line index
    to {"konto", "momskod"} — the BAS + moms coding, persisted per line, from
    which a balanced verifikat is built and stored. Returns the updated result,
    or None if the invoice does not exist."""
    _ensure()
    with _write_lock, db.connect() as c:
        if c.execute("SELECT 1 FROM invoices WHERE id=?", (invoice_id,)).fetchone() is None:
            return None

        for key, new_value in field_values.items():
            row = c.execute(
                "SELECT value FROM fields WHERE invoice_id=? AND key=?", (invoice_id, key)
            ).fetchone()
            if row is None:
                continue
            old = row["value"]
            if new_value != old:
                c.execute(
                    "UPDATE fields SET value=?, status='green' WHERE invoice_id=? AND key=?",
                    (new_value, invoice_id, key),
                )
                _append_audit(c, invoice_id, actor, "field_corrected",
                              field_key=key, old_value=old, new_value=new_value)

        for idx, code in projects.items():
            row = c.execute(
                "SELECT project FROM line_items WHERE invoice_id=? AND idx=?",
                (invoice_id, int(idx)),
            ).fetchone()
            if row is None:
                continue
            old = row["project"]
            if code != old:
                c.execute(
                    "UPDATE line_items SET project=? WHERE invoice_id=? AND idx=?",
                    (code, invoice_id, int(idx)),
                )
                _append_audit(c, invoice_id, actor, "project_assigned",
                              field_key=f"row:{idx}", old_value=old or None, new_value=code)

        for idx, kod in (codings or {}).items():
            konto = (kod.get("konto") or "").strip()
            momskod = (kod.get("momskod") or "").strip()
            row = c.execute(
                "SELECT konto, momskod FROM line_items WHERE invoice_id=? AND idx=?",
                (invoice_id, int(idx)),
            ).fetchone()
            if row is None:
                continue
            if (konto, momskod) != (row["konto"], row["momskod"]):
                c.execute(
                    "UPDATE line_items SET konto=?, momskod=? WHERE invoice_id=? AND idx=?",
                    (konto, momskod, invoice_id, int(idx)),
                )
                _append_audit(c, invoice_id, actor, "kontering_satt",
                              field_key=f"row:{idx}",
                              old_value=f"{row['konto']}/{row['momskod']}".strip("/") or None,
                              new_value=f"{konto}/{momskod}")

        # Bygg och lagra verifikatet av de konterade raderna (BAS + moms).
        verifikat_json, ver_note = _bygg_verifikat_json(c, invoice_id)
        c.execute("UPDATE invoices SET verifikat_json=? WHERE id=?",
                  (verifikat_json, invoice_id))
        if ver_note:
            _append_audit(c, invoice_id, actor, "verifikat_byggt", note=ver_note)

        c.execute("UPDATE invoices SET verified=1, verified_at=?, verified_by=? WHERE id=?",
                  (_now(), actor, invoice_id))
        _append_audit(c, invoice_id, actor, "verified")

        # Granskning klar (granskaren har kodat och verifierat). Nollställ ev.
        # tidigare attest — ändrad kontering måste attesteras på nytt.
        c.execute("UPDATE invoices SET attest_status='granskad', granskare=?, "
                  "granskad_at=?, attestant=NULL, attesterad_at=NULL, "
                  "attest_kommentar=NULL WHERE id=?",
                  (actor, _now(), invoice_id))
        _append_audit(c, invoice_id, actor, "granskad")

    return get_result(invoice_id)


class AttestError(Exception):
    """Attesten kan inte utföras (fel status, fyra ögon, beloppsgräns)."""


def _leverantorsskuld(verifikat_json: str | None) -> Decimal:
    if not verifikat_json:
        return Decimal("0")
    ver = json.loads(verifikat_json)
    return sum((Decimal(r["kredit"]) for r in ver["rader"]
                if r["konto"] == bas.LEVERANTORSSKULDER), Decimal("0"))


def attestera(invoice_id: str, attestant: str, actor: str,
              beloppsgrans: Decimal | None = None) -> dict | None:
    """Attestera en granskad faktura. Kräver fyra-ögon (attestant ≠ granskare)
    och att beloppet ryms inom beloppsgränsen. Lägger handover i outboxen — först
    attesterade fakturor lämnas över/betalas."""
    _ensure()
    attestant = (attestant or "").strip()
    if not attestant:
        raise AttestError("attestant saknas")
    with _write_lock, db.connect() as c:
        inv = c.execute(
            "SELECT attest_status, granskare, verifikat_json FROM invoices WHERE id=?",
            (invoice_id,)).fetchone()
        if inv is None:
            return None
        if inv["attest_status"] != "granskad":
            raise AttestError(f"fakturan är inte granskad (status: {inv['attest_status']})")
        if attestant == (inv["granskare"] or ""):
            raise AttestError("attestant får inte vara samma som granskare (fyra ögon)")
        belopp = _leverantorsskuld(inv["verifikat_json"])
        if beloppsgrans is not None and belopp > beloppsgrans:
            raise AttestError(
                f"beloppet {belopp} överstiger attestantens beloppsgräns {beloppsgrans}")

        c.execute("UPDATE invoices SET attest_status='attesterad', attestant=?, "
                  "attesterad_at=? WHERE id=?", (attestant, _now(), invoice_id))
        _append_audit(c, invoice_id, attestant, "attesterad",
                      new_value=f"{belopp}")

        # Först nu läggs handover i outboxen (idempotent på fakturans fingerprint).
        payload = _handover_payload(c, invoice_id)
        c.execute(
            "INSERT OR IGNORE INTO outbox(invoice_id, idempotency_key, status, "
            "attempts, next_attempt_at, payload_json, created_at) "
            "VALUES(?,?,'pending',0,?,?,?)",
            (invoice_id, invoice_id, _now(), json.dumps(payload), _now()),
        )
        if c.execute("SELECT changes()").fetchone()[0]:
            c.execute("UPDATE invoices SET handover_status='pending' WHERE id=?", (invoice_id,))
            _append_audit(c, invoice_id, attestant, "handover_queued")
    return get_result(invoice_id)


def avvisa(invoice_id: str, actor: str, kommentar: str = "") -> dict | None:
    """Avvisa en faktura (skickas tillbaka för omkontering)."""
    _ensure()
    with _write_lock, db.connect() as c:
        if c.execute("SELECT 1 FROM invoices WHERE id=?", (invoice_id,)).fetchone() is None:
            return None
        c.execute("UPDATE invoices SET attest_status='avvisad', attest_kommentar=? WHERE id=?",
                  (kommentar or None, invoice_id))
        _append_audit(c, invoice_id, actor, "avvisad", new_value=kommentar or None)
    return get_result(invoice_id)


def _bygg_verifikat_json(c, invoice_id: str) -> tuple[str | None, str | None]:
    """Bygg verifikatet av de konterade raderna. Returnerar (json, notering).

    Bara rader med både konto och momskod tas med. Om ingen rad är konterad,
    eller om något är ogiltigt, lagras inget verifikat (json=None) och en
    notering förklarar varför."""
    rader = []
    for r in c.execute("SELECT idx, amount, konto, momskod, description "
                       "FROM line_items WHERE invoice_id=? ORDER BY idx", (invoice_id,)):
        if not r["konto"] or not r["momskod"]:
            continue
        netto = validation.parse_amount(r["amount"] or "")
        if netto is None:
            return None, f"rad {r['idx']}: kunde inte tolka beloppet {r['amount']!r}"
        rader.append(kontering.Konteringsrad(
            konto=r["konto"], netto=netto, momskod=r["momskod"],
            beskrivning=r["description"] or ""))
    if not rader:
        return None, "inga konterade rader (konto + momskod saknas)"
    try:
        total = _decimal_or_none(
            c.execute("SELECT value FROM fields WHERE invoice_id=? AND key='total_amount'",
                      (invoice_id,)).fetchone())
        ver = kontering.bygg_verifikat(rader, total)
    except (KeyError, ValueError, AssertionError) as e:
        return None, f"kunde inte bygga verifikat: {e}"
    return json.dumps(kontering.som_dict(ver)), f"{len(rader)} rader konterade"


def _decimal_or_none(row) -> Decimal | None:
    if row is None:
        return None
    return validation.parse_amount(row["value"] or "")


def _handover_payload(c, invoice_id: str) -> dict:
    """The coded invoice as the target needs it: header values plus the
    allocation lines (each row's project, konto, momskod + amount)."""
    fv = {r["key"]: r["value"] for r in
          c.execute("SELECT key, value FROM fields WHERE invoice_id=?", (invoice_id,))}
    lines = [
        {"project": r["project"], "konto": r["konto"], "momskod": r["momskod"],
         "amount": r["amount"], "description": r["description"]}
        for r in c.execute(
            "SELECT project, konto, momskod, amount, description FROM line_items "
            "WHERE invoice_id=? ORDER BY idx", (invoice_id,))
    ]
    return {
        "invoice_id": invoice_id,
        "supplier": fv.get("supplier_name", ""),
        "invoice_number": fv.get("invoice_number", ""),
        "invoice_date": fv.get("invoice_date", ""),
        "due_date": fv.get("due_date", ""),
        "currency": fv.get("currency", ""),
        "net": fv.get("net_amount", ""),
        "vat": fv.get("vat_amount", ""),
        "total": fv.get("total_amount", ""),
        "vat_number": fv.get("vat_number", ""),
        "iban": fv.get("iban", ""),
        "payment_reference": fv.get("payment_reference", ""),
        "allocation_lines": lines,
    }


def verifikat_for_export(invoice_id: str | None = None) -> list[dict]:
    """Konterade verifikat att SIE-exportera. Ett id ger en faktura, annars alla
    med ett byggt verifikat (äldst först, som de ska bokföras)."""
    _ensure()
    with db.connect() as c:
        if invoice_id is not None:
            invs = c.execute(
                "SELECT id, supplier, verifikat_json FROM invoices "
                "WHERE id=? AND verifikat_json IS NOT NULL "
                "AND attest_status='attesterad'", (invoice_id,)).fetchall()
        else:
            invs = c.execute(
                "SELECT id, supplier, verifikat_json FROM invoices "
                "WHERE verifikat_json IS NOT NULL AND attest_status='attesterad' "
                "ORDER BY created_at").fetchall()
        out = []
        for inv in invs:
            fv = {r["key"]: r["value"] for r in c.execute(
                "SELECT key, value FROM fields WHERE invoice_id=?", (inv["id"],))}
            out.append({
                "id": inv["id"],
                "supplier": inv["supplier"] or fv.get("supplier_name", ""),
                "invoice_number": fv.get("invoice_number", ""),
                "invoice_date": fv.get("invoice_date", ""),
                "verifikat": json.loads(inv["verifikat_json"]),
            })
        return out


def betalunderlag(invoice_id: str | None = None) -> list[dict]:
    """Betalunderlag för pain.001: konterade fakturor med belopp att betala
    (leverantörsskulden, 2440, från verifikatet), mottagarens IBAN och OCR."""
    _ensure()
    with db.connect() as c:
        if invoice_id is not None:
            invs = c.execute(
                "SELECT id, supplier, verifikat_json FROM invoices "
                "WHERE id=? AND verifikat_json IS NOT NULL "
                "AND attest_status='attesterad'", (invoice_id,)).fetchall()
        else:
            invs = c.execute(
                "SELECT id, supplier, verifikat_json FROM invoices "
                "WHERE verifikat_json IS NOT NULL AND attest_status='attesterad' "
                "ORDER BY created_at").fetchall()
        out = []
        for inv in invs:
            fv = {r["key"]: r["value"] for r in c.execute(
                "SELECT key, value FROM fields WHERE invoice_id=?", (inv["id"],))}
            ver = json.loads(inv["verifikat_json"])
            belopp = sum((Decimal(r["kredit"]) for r in ver["rader"]
                          if r["konto"] == bas.LEVERANTORSSKULDER), Decimal("0"))
            out.append({
                "id": inv["id"],
                "supplier": inv["supplier"] or fv.get("supplier_name", ""),
                "invoice_number": fv.get("invoice_number", ""),
                "due_date": fv.get("due_date", ""),
                "currency": fv.get("currency", "") or "SEK",
                "iban": (fv.get("iban", "") or "").replace(" ", ""),
                "bankgiro": "".join(c for c in fv.get("bankgiro", "") if c.isdigit()),
                "plusgiro": "".join(c for c in fv.get("plusgiro", "") if c.isdigit()),
                "payment_reference": fv.get("payment_reference", ""),
                "belopp": f"{belopp:.2f}",
            })
        return out


# ---- outbox / Marathon handover ----

def due_outbox(limit: int = 10) -> list[dict]:
    _ensure()
    now = _now()
    with db.connect() as c:
        rows = c.execute(
            "SELECT * FROM outbox WHERE status='pending' AND "
            "(next_attempt_at IS NULL OR next_attempt_at<=?) ORDER BY id LIMIT ?",
            (now, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def mark_delivered(outbox_id: int, invoice_id: str, ref: str, attempt: int) -> None:
    _ensure()
    with _write_lock, db.connect() as c:
        c.execute(
            "UPDATE outbox SET status='delivered', marathon_ref=?, attempts=?, "
            "delivered_at=?, last_error=NULL WHERE id=?",
            (ref, attempt, _now(), outbox_id),
        )
        c.execute("UPDATE invoices SET handover_status='delivered', marathon_ref=? WHERE id=?",
                  (ref, invoice_id))
        _append_audit(c, invoice_id, "marathon", "handed_over", new_value=ref)


def mark_failed(outbox_id: int, invoice_id: str, attempt: int, error: str) -> None:
    _ensure()
    terminal = attempt >= MAX_HANDOVER_ATTEMPTS
    with _write_lock, db.connect() as c:
        if terminal:
            c.execute(
                "UPDATE outbox SET status='failed', attempts=?, last_error=?, "
                "next_attempt_at=NULL WHERE id=?",
                (attempt, error, outbox_id),
            )
            c.execute("UPDATE invoices SET handover_status='failed' WHERE id=?", (invoice_id,))
            _append_audit(c, invoice_id, "marathon", "handover_failed", new_value=error)
        else:
            backoff = min(60, 2 ** attempt)
            next_at = (datetime.now(timezone.utc) + timedelta(seconds=backoff)) \
                .isoformat(timespec="seconds")
            c.execute(
                "UPDATE outbox SET attempts=?, last_error=?, next_attempt_at=? WHERE id=?",
                (attempt, error, next_at, outbox_id),
            )


def get_handover(invoice_id: str) -> dict:
    _ensure()
    with db.connect() as c:
        r = c.execute(
            "SELECT status, attempts, last_error, marathon_ref, delivered_at "
            "FROM outbox WHERE invoice_id=?", (invoice_id,),
        ).fetchone()
    return dict(r) if r else {"status": "none"}
