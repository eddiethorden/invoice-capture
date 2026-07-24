"""Accounts Payable module — receives approved invoices and lists them as payables.

A separate service from the invoice-scanning backend. It exposes an intake API
modelled on Fortnox's "create custom document" endpoint and keeps its own store
of payables, with a simple list page for the AP clerk.

  Intake (scanning module -> AP):
    POST /ap/custom-documents   {category, referenceType, externalId, document}
      -> 201 {created: 1|0, reference, id}         (idempotent by externalId)
      -> 400 {error: "referenceTypeNotAllowed"}    (Fortnox's rule, enforced here)

  Read (AP clerk):
    GET  /ap/payables            list of payables (JSON)
    GET  /ap/payables/{id}       one payable with its full document
    GET  /                       payables list page (auto-refreshing)

Run it:
    cd backend && source .venv/bin/activate
    uvicorn ap_module:app --port 8010

Point the scanning backend at it with:
    HANDOVER_TARGET=accounts_payable
    AP_INTAKE_URL=http://localhost:8010/ap/custom-documents   (default)
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

app = FastAPI(title="Accounts Payable")

DB_PATH = Path(__file__).resolve().parent / "data" / "ap.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


# ---- store ----

def _db() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _init() -> None:
    with _db() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS payables (
                id             TEXT PRIMARY KEY,   -- externalId from intake
                reference      TEXT NOT NULL,      -- AP-XXXXXXXX
                reference_type TEXT NOT NULL,
                category       TEXT NOT NULL,
                supplier       TEXT,
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
    return "AP-" + hashlib.sha256(external_id.encode()).hexdigest()[:8].upper()


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
    """A received payable is 'open'; past its due date it's 'overdue'. (No
    payment execution in this module, so those are the only states.)"""
    d = _parse_date(due_date)
    if d is not None and d < date.today():
        return "overdue"
    return "open"


# ---- intake API (Fortnox custom-document shaped) ----

@app.post("/ap/custom-documents", status_code=201)
def create_custom_document(body: dict):
    category = (body.get("category") or "").upper()
    reference_type = body.get("referenceType") or ""
    external_id = body.get("externalId") or ""
    document = body.get("document") or {}

    if category not in ("INBOUND", "OUTBOUND"):
        return JSONResponse(status_code=400,
                            content={"error": "category must be INBOUND or OUTBOUND"})
    if not reference_type_allowed(reference_type):
        return JSONResponse(status_code=400,
                            content={"error": "referenceTypeNotAllowed",
                                     "referenceType": reference_type})
    if not external_id:
        return JSONResponse(status_code=400, content={"error": "externalId is required"})

    reference = _reference(external_id)
    with _db() as c:
        existing = c.execute("SELECT reference FROM payables WHERE id=?",
                             (external_id,)).fetchone()
        if existing:
            # Idempotent: already received — update the document, keep the payable.
            c.execute("UPDATE payables SET document_json=?, "
                      "supplier=?, invoice_number=?, invoice_date=?, due_date=?, "
                      "currency=?, total=?, vat=?, net=?, payment_reference=?, status=? "
                      "WHERE id=?",
                      (json.dumps(document, ensure_ascii=False),
                       document.get("supplier"), document.get("invoice_number"),
                       document.get("invoice_date"), document.get("due_date"),
                       document.get("currency"), document.get("total"),
                       document.get("vat"), document.get("net"),
                       document.get("payment_reference"),
                       _status(document.get("due_date")), external_id))
            return {"created": 0, "reference": existing["reference"], "id": external_id}

        c.execute("INSERT INTO payables (id, reference, reference_type, category, "
                  "supplier, invoice_number, invoice_date, due_date, currency, total, "
                  "vat, net, payment_reference, status, received_at, document_json) "
                  "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (external_id, reference, reference_type, category,
                   document.get("supplier"), document.get("invoice_number"),
                   document.get("invoice_date"), document.get("due_date"),
                   document.get("currency"), document.get("total"),
                   document.get("vat"), document.get("net"),
                   document.get("payment_reference"),
                   _status(document.get("due_date")), _now(),
                   json.dumps(document, ensure_ascii=False)))
    return {"created": 1, "reference": reference, "id": external_id}


# ---- read API ----

_LIST_COLS = ("id", "reference", "supplier", "invoice_number", "invoice_date",
              "due_date", "currency", "total", "vat", "status", "received_at")


@app.get("/ap/payables")
def list_payables() -> list[dict]:
    with _db() as c:
        rows = c.execute(
            f"SELECT {', '.join(_LIST_COLS)} FROM payables "
            "ORDER BY due_date IS NULL, due_date, received_at DESC").fetchall()
    return [dict(r) for r in rows]


@app.get("/ap/payables/{payable_id}")
def get_payable(payable_id: str):
    with _db() as c:
        r = c.execute("SELECT * FROM payables WHERE id=?", (payable_id,)).fetchone()
    if not r:
        return JSONResponse(status_code=404, content={"error": "not found"})
    d = dict(r)
    d["document"] = json.loads(d.pop("document_json"))
    return d


# ---- list page ----

@app.get("/", response_class=HTMLResponse)
def home() -> str:
    payables = list_payables()
    open_n = sum(1 for p in payables if p["status"] == "open")
    overdue_n = sum(1 for p in payables if p["status"] == "overdue")
    rows = []
    for p in payables:
        badge = ("overdue" if p["status"] == "overdue" else "open")
        rows.append(f"""
        <tr>
          <td class="ref">{_esc(p['reference'])}</td>
          <td>{_esc(p['supplier'] or '—')}</td>
          <td>{_esc(p['invoice_number'] or '—')}</td>
          <td class="num">{_esc(p['total'] or '—')} {_esc(p['currency'] or '')}</td>
          <td>{_esc(p['due_date'] or '—')}</td>
          <td><span class="badge {badge}">{badge}</span></td>
          <td class="t">{_esc(p['received_at'])}</td>
        </tr>""")
    body = "\n".join(rows) or ("<tr><td colspan='7' class='empty'>No payables yet. "
                               "Approve an invoice in the scanning app.</td></tr>")
    return f"""<!doctype html><html><head><meta charset="utf-8">
    <title>Accounts Payable — payables</title>
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
      .ref{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;color:#0969da}}
      .num{{text-align:right;white-space:nowrap}} .t{{color:#8c959f;font-size:12px}}
      .badge{{padding:2px 8px;border-radius:999px;font-size:11px;font-weight:600}}
      .badge.open{{background:#dafbe1;color:#1a7f37}}
      .badge.overdue{{background:#ffebe9;color:#cf222e}}
      .empty{{color:#656d76;text-align:center;padding:28px}}
    </style></head><body>
    <h1>Accounts Payable</h1>
    <div class="sub">Payables received from invoice capture · auto-refreshes every 4s</div>
    <div class="stats">
      <div class="stat"><b>{len(payables)}</b><span>total</span></div>
      <div class="stat"><b>{open_n}</b><span>open</span></div>
      <div class="stat"><b>{overdue_n}</b><span>overdue</span></div>
    </div>
    <table>
      <thead><tr><th>Ref</th><th>Supplier</th><th>Invoice #</th><th>Amount</th>
        <th>Due</th><th>Status</th><th>Received</th></tr></thead>
      <tbody>{body}</tbody>
    </table>
    </body></html>"""


def _esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            if s is not None else "")
