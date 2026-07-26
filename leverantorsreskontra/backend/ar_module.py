"""Accounts Receivable module — receives issued customer invoices and lists them
as receivables (money owed to us).

The OUTBOUND counterpart to the Accounts Payable module. Same shape: an intake
API modelled on Fortnox's "create custom document" endpoint, its own store of
receivables, and a simple list page for the AR clerk. A receivable is fed by a
billing/customer-invoicing producer (not the supplier-invoice scanner, which
feeds Payables), posted as an OUTBOUND custom document.

  Intake (producer -> AR):
    POST /ar/custom-documents   {category, referenceType, externalId, document}
      -> 201 {created: 1|0, reference, id}         (idempotent by externalId)
      -> 400 {error: "referenceTypeNotAllowed"}    (Fortnox's rule, enforced here)
      -> 400 {error: "category must be OUTBOUND"}   (AR only accepts OUTBOUND)

  Read (AR clerk):
    GET  /ar/receivables         list of receivables (JSON)
    GET  /ar/receivables/{id}    one receivable with its full document
    GET  /                       receivables list page (auto-refreshing)

Run it:
    cd backend && source .venv/bin/activate
    uvicorn ar_module:app --port 8020
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from datetime import date, datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from custom_doc_types import reference_type_allowed

app = FastAPI(title="Accounts Receivable")

DB_PATH = Path(__file__).resolve().parent / "data" / "ar.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


# ---- store ----

def _db() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _init() -> None:
    with _db() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS receivables (
                id             TEXT PRIMARY KEY,   -- externalId from intake
                reference      TEXT NOT NULL,      -- AR-XXXXXXXX
                reference_type TEXT NOT NULL,
                category       TEXT NOT NULL,
                customer       TEXT,
                invoice_number TEXT,
                invoice_date   TEXT,
                due_date       TEXT,
                currency       TEXT,
                total          TEXT,
                vat            TEXT,
                net            TEXT,
                payment_reference TEXT,
                status         TEXT NOT NULL,
                received_at    TEXT NOT NULL,
                document_json  TEXT NOT NULL
            )
        """)


_init()


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _reference(external_id: str) -> str:
    return "AR-" + hashlib.sha256(external_id.encode()).hexdigest()[:8].upper()


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _status(due_date: str | None) -> str:
    """A receivable is 'open'; past its due date it's 'overdue'. (No cash
    application in this module, so those are the only states.)"""
    d = _parse_date(due_date)
    if d is not None and d < date.today():
        return "overdue"
    return "open"


# ---- intake API (Fortnox custom-document shaped) ----

@app.post("/ar/custom-documents", status_code=201)
def create_custom_document(body: dict):
    category = (body.get("category") or "").upper()
    reference_type = body.get("referenceType") or ""
    external_id = body.get("externalId") or ""
    document = body.get("document") or {}

    if category != "OUTBOUND":
        return JSONResponse(status_code=400,
                            content={"error": "category must be OUTBOUND"})
    if not reference_type_allowed(reference_type):
        return JSONResponse(status_code=400,
                            content={"error": "referenceTypeNotAllowed",
                                     "referenceType": reference_type})
    if not external_id:
        return JSONResponse(status_code=400, content={"error": "externalId is required"})

    reference = _reference(external_id)
    with _db() as c:
        existing = c.execute("SELECT reference FROM receivables WHERE id=?",
                             (external_id,)).fetchone()
        if existing:
            # Idempotent: already received — update the document, keep the receivable.
            c.execute("UPDATE receivables SET document_json=?, "
                      "customer=?, invoice_number=?, invoice_date=?, due_date=?, "
                      "currency=?, total=?, vat=?, net=?, payment_reference=?, status=? "
                      "WHERE id=?",
                      (json.dumps(document, ensure_ascii=False),
                       document.get("customer"), document.get("invoice_number"),
                       document.get("invoice_date"), document.get("due_date"),
                       document.get("currency"), document.get("total"),
                       document.get("vat"), document.get("net"),
                       document.get("payment_reference"),
                       _status(document.get("due_date")), external_id))
            return {"created": 0, "reference": existing["reference"], "id": external_id}

        c.execute("INSERT INTO receivables (id, reference, reference_type, category, "
                  "customer, invoice_number, invoice_date, due_date, currency, total, "
                  "vat, net, payment_reference, status, received_at, document_json) "
                  "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (external_id, reference, reference_type, category,
                   document.get("customer"), document.get("invoice_number"),
                   document.get("invoice_date"), document.get("due_date"),
                   document.get("currency"), document.get("total"),
                   document.get("vat"), document.get("net"),
                   document.get("payment_reference"),
                   _status(document.get("due_date")), _now(),
                   json.dumps(document, ensure_ascii=False)))
    return {"created": 1, "reference": reference, "id": external_id}


# ---- read API ----

_LIST_COLS = ("id", "reference", "customer", "invoice_number", "invoice_date",
              "due_date", "currency", "total", "vat", "status", "received_at")


@app.get("/ar/receivables")
def list_receivables() -> list[dict]:
    with _db() as c:
        rows = c.execute(
            f"SELECT {', '.join(_LIST_COLS)} FROM receivables "
            "ORDER BY received_at DESC, reference").fetchall()
    return [dict(r) for r in rows]


@app.get("/ar/receivables/{receivable_id}")
def get_receivable(receivable_id: str):
    with _db() as c:
        r = c.execute("SELECT * FROM receivables WHERE id=?", (receivable_id,)).fetchone()
    if not r:
        return JSONResponse(status_code=404, content={"error": "not found"})
    d = dict(r)
    d["document"] = json.loads(d.pop("document_json"))
    return d


# ---- list page ----

@app.get("/", response_class=HTMLResponse)
def home() -> str:
    receivables = list_receivables()
    open_n = sum(1 for r in receivables if r["status"] == "open")
    overdue_n = sum(1 for r in receivables if r["status"] == "overdue")
    rows = []
    for r in receivables:
        badge = ("overdue" if r["status"] == "overdue" else "open")
        rows.append(f"""
        <tr>
          <td class="ref">{_esc(r['reference'])}</td>
          <td>{_esc(r['customer'] or '—')}</td>
          <td>{_esc(r['invoice_number'] or '—')}</td>
          <td class="num">{_esc(r['total'] or '—')} {_esc(r['currency'] or '')}</td>
          <td>{_esc(r['due_date'] or '—')}</td>
          <td><span class="badge {badge}">{'förfallen' if badge == 'overdue' else 'öppen'}</span></td>
          <td class="t">{_esc(r['received_at'])}</td>
        </tr>""")
    body = "\n".join(rows) or ("<tr><td colspan='7' class='empty'>Inga kundfordringar än. "
                               "Posta en kundfaktura till intake-API:et.</td></tr>")
    return f"""<!doctype html><html><head><meta charset="utf-8">
    <title>Kundreskontra — kundfordringar</title>
    <meta http-equiv="refresh" content="4">
    <style>
      body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:24px;color:#1f2328;background:#f6f8fa}}
      h1{{font-size:20px;margin-bottom:4px}} .sub{{color:#656d76;margin-bottom:16px}}
      .stats{{display:flex;gap:10px;margin-bottom:16px}}
      .stat{{background:#fff;border:1px solid #d0d7de;border-radius:8px;padding:8px 14px}}
      .stat b{{font-size:20px;display:block}} .stat span{{color:#656d76;font-size:12px}}
      table{{width:100%;border-collapse:collapse;background:#fff;border:1px solid #d0d7de;border-radius:8px;overflow:hidden}}
      th,td{{padding:9px 12px;text-align:left;border-bottom:1px solid #eaeef2;font-size:13.5px}}
      th{{background:#f6f8fa;color:#656d76;font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.03em}}
      tr:last-child td{{border-bottom:none}}
      .ref{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;color:#8250df}}
      .num{{text-align:right;white-space:nowrap}} .t{{color:#8c959f;font-size:12px}}
      .badge{{padding:2px 8px;border-radius:999px;font-size:11px;font-weight:600}}
      .badge.open{{background:#dafbe1;color:#1a7f37}}
      .badge.overdue{{background:#ffebe9;color:#cf222e}}
      .empty{{color:#656d76;text-align:center;padding:28px}}
    </style></head><body>
    <h1>Kundreskontra</h1>
    <div class="sub">Kundfakturor som är skyldiga oss · uppdateras var 4:e sekund</div>
    <div class="stats">
      <div class="stat"><b>{len(receivables)}</b><span>totalt</span></div>
      <div class="stat"><b>{open_n}</b><span>öppna</span></div>
      <div class="stat"><b>{overdue_n}</b><span>förfallna</span></div>
    </div>
    <table>
      <thead><tr><th>Ref</th><th>Kund</th><th>Fakturanr</th><th>Belopp</th>
        <th>Förfaller</th><th>Status</th><th>Mottagen</th></tr></thead>
      <tbody>{body}</tbody>
    </table>
    </body></html>"""


def _esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            if s is not None else "")
