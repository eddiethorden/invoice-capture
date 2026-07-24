"""A tiny stand-in for the Fortnox API, for checking what our adapter transmits.

It implements the endpoints the adapter calls, returns plausible Fortnox-shaped
responses, and records every request so you can inspect exactly what was sent —
the SupplierInvoice JSON, the uploaded PDF, and the file link.

Run it:
    cd backend && source .venv/bin/activate
    uvicorn fake_fortnox:app --port 8899

Then point the app at it and deliver (see the manual / the chat instructions):
    HANDOVER_TARGET=fortnox
    FORTNOX_CLIENT_ID=test  FORTNOX_CLIENT_SECRET=test
    FORTNOX_AUTH_URL=http://localhost:8899/oauth-v1/auth
    FORTNOX_TOKEN_URL=http://localhost:8899/oauth-v1/token
    FORTNOX_API_BASE=http://localhost:8899/3

Inspect what was received at  http://localhost:8899/
"""

from __future__ import annotations

import json
import secrets
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

app = FastAPI(title="Fake Fortnox")

UPLOADS = Path(__file__).resolve().parent / "data" / "fake_fortnox_uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)

CAPTURES: list[dict] = []
_counter = {"invoice": 1000, "file": 0}


def _capture(request: Request, summary: str, body) -> None:
    CAPTURES.insert(0, {
        "seq": len(CAPTURES) + 1,
        "at": time.strftime("%H:%M:%S"),
        "method": request.method,
        "path": request.url.path,
        "query": dict(request.query_params),
        "authorization": "Bearer …" if request.headers.get("authorization") else None,
        "content_type": request.headers.get("content-type", ""),
        "summary": summary,
        "body": body,
    })


# ---- OAuth ----

@app.get("/oauth-v1/auth")
def authorize(request: Request):
    """Fortnox would show a consent screen; we just redirect straight back with a
    fake code so the connect flow completes locally."""
    redirect_uri = request.query_params.get("redirect_uri", "")
    state = request.query_params.get("state", "")
    _capture(request, "authorize -> redirect back with code", dict(request.query_params))
    sep = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(f"{redirect_uri}{sep}code=fake-auth-code&state={state}")


@app.post("/oauth-v1/token")
async def token(request: Request):
    form = dict(await request.form())
    _capture(request, f"token grant: {form.get('grant_type')}", form)
    return {
        "access_token": "fake-access-" + secrets.token_hex(4),
        "refresh_token": "fake-refresh-" + secrets.token_hex(4),  # rotated each call
        "token_type": "Bearer",
        "expires_in": 3600,
        "scope": "supplierinvoice inbox",
    }


# ---- API ----

@app.get("/3/suppliers")
def suppliers(request: Request):
    orgnr = request.query_params.get("organisationnumber")
    _capture(request, f"supplier lookup (org {orgnr})", None)
    return {"Suppliers": [{
        "SupplierNumber": "1",
        "Name": "Test Supplier AB",
        "OrganisationNumber": orgnr or "556000-0000",
    }]}


@app.post("/3/inbox")
async def inbox(request: Request):
    form = await request.form()
    upload = form.get("file")
    saved, size, name = None, 0, None
    if upload is not None:
        data = await upload.read()
        size, name = len(data), upload.filename
        _counter["file"] += 1
        saved = UPLOADS / f"{_counter['file']:03d}_{name}"
        saved.write_bytes(data)
    file_id = f"fake-file-{_counter['file']}"
    _capture(request, f"PDF uploaded to inbox ({name}, {size} bytes -> {saved})",
             {"filename": name, "size_bytes": size, "saved_to": str(saved), "file_id": file_id})
    return {"File": {"Id": file_id, "Name": name}}


@app.post("/3/supplierinvoices")
async def create_supplier_invoice(request: Request):
    body = await request.json()
    _counter["invoice"] += 1
    number = _counter["invoice"]
    _capture(request, f"SupplierInvoice created (GivenNumber {number})", body)
    inv = dict(body.get("SupplierInvoice", {}))
    inv["GivenNumber"] = number
    return {"SupplierInvoice": inv}


@app.post("/3/supplierinvoicefileconnections")
async def file_connection(request: Request):
    body = await request.json()
    _capture(request, "PDF linked to SupplierInvoice", body)
    return {"SupplierInvoiceFileConnection": body.get("SupplierInvoiceFileConnection", {})}


# ---- inspection ----

@app.get("/captures")
def captures() -> list[dict]:
    return CAPTURES


@app.post("/reset")
def reset() -> dict:
    CAPTURES.clear()
    return {"cleared": True}


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    rows = []
    for c in CAPTURES:
        body = json.dumps(c["body"], indent=2, ensure_ascii=False) if c["body"] is not None else ""
        rows.append(f"""
        <div class="cap">
          <div class="hd"><span class="m">{c['method']}</span> <code>{c['path']}</code>
            <span class="s">{c['summary']}</span><span class="t">{c['at']}</span></div>
          {'<pre>' + _esc(body) + '</pre>' if body else ''}
        </div>""")
    body = "\n".join(rows) or "<p class='empty'>No requests captured yet. Deliver an invoice, then refresh.</p>"
    return f"""<!doctype html><html><head><meta charset="utf-8">
    <title>Fake Fortnox — captured requests</title>
    <meta http-equiv="refresh" content="3">
    <style>
      body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:24px;color:#1f2328;background:#f6f8fa}}
      h1{{font-size:20px}} .sub{{color:#656d76;margin-bottom:18px}}
      .cap{{background:#fff;border:1px solid #d0d7de;border-radius:8px;margin-bottom:12px;overflow:hidden}}
      .hd{{padding:8px 12px;background:#f6f8fa;border-bottom:1px solid #d0d7de;display:flex;gap:10px;align-items:center}}
      .m{{font-weight:700;color:#0969da}} .s{{color:#1a7f37;flex:1}} .t{{color:#8c959f;font-size:12px}}
      code{{background:#eaeef2;padding:1px 6px;border-radius:4px}}
      pre{{margin:0;padding:12px;font-size:12.5px;overflow:auto;white-space:pre-wrap}}
      .empty{{color:#656d76}}
    </style></head><body>
    <h1>Fake Fortnox — captured requests</h1>
    <div class="sub">Newest first · auto-refreshes every 3s · uploads saved to
      <code>{UPLOADS}</code></div>
    {body}
    </body></html>"""


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
