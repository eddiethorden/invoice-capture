"""Handover adapter for Fortnox (a real Swedish accounting/ERP system).

A drop-in alternative to the Marathon adapter, selected with HANDOVER_TARGET=
fortnox. It implements the documented supplier-invoice scanning flow:

  1. upload the original PDF to the Inbox (supplier-invoice folder, inbox_s)
  2. POST a SupplierInvoice with the extracted, coded fields
  3. link the PDF to the created invoice via SupplierInvoiceFileConnections

Authentication is OAuth2 Authorization Code Flow (the static API-token method was
deprecated in April 2025). The critical gotchas are handled here:

  * access_type=offline is requested so we get a refresh token at all;
  * refresh tokens are ROTATED on every use, so the new one is stored after each
    refresh (an integration that forgets this stops working after 45 days);
  * access tokens live 1 hour and are refreshed ~60s before expiry;
  * 429 (rate limit, 25 req / 5 s) and 5xx are raised as transient so the outbox
    worker backs off and retries.

Client-specific mapping (chart of accounts, the supplier register, project
codes) is intentionally configurable — see FORTNOX_DEFAULT_ACCOUNT /
FORTNOX_DEFAULT_SUPPLIER and the notes below.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from urllib.parse import urlencode

import httpx

from . import store
from .validation import parse_amount

log = logging.getLogger("invoice.fortnox")

AUTH_URL = "https://apps.fortnox.se/oauth-v1/auth"
TOKEN_URL = "https://apps.fortnox.se/oauth-v1/token"
API_BASE = "https://api.fortnox.se/3"

# Test seam: an httpx transport to route requests through (set by tests).
_transport = None


# Base URLs are overridable so the adapter can be pointed at a Fortnox sandbox
# or the bundled fake Fortnox server for inspecting what gets transmitted.
def _auth_url() -> str:
    return os.environ.get("FORTNOX_AUTH_URL", AUTH_URL)


def _token_url() -> str:
    return os.environ.get("FORTNOX_TOKEN_URL", TOKEN_URL)


def _api_base() -> str:
    return os.environ.get("FORTNOX_API_BASE", API_BASE)


class FortnoxAuthError(Exception):
    """Not configured or not connected — needs authorization."""


class FortnoxTransient(Exception):
    """Rate limit or server error — the outbox should retry."""


class FortnoxError(Exception):
    """A permanent problem with the request or mapping."""


# ---- configuration ----

def client_id() -> str | None:
    return os.environ.get("FORTNOX_CLIENT_ID")


def client_secret() -> str | None:
    return os.environ.get("FORTNOX_CLIENT_SECRET")


def redirect_uri() -> str:
    return os.environ.get("FORTNOX_REDIRECT_URI",
                          "http://localhost:8000/api/fortnox/callback")


def scopes() -> str:
    return os.environ.get("FORTNOX_SCOPES", "supplierinvoice inbox")


def _token_path() -> Path:
    return Path(os.environ.get("FORTNOX_TOKEN_PATH", store.DATA_DIR / "fortnox_tokens.json"))


def _ledger_path() -> Path:
    return Path(os.environ.get("FORTNOX_LEDGER_PATH", store.DATA_DIR / "fortnox_delivered.json"))


def _http() -> httpx.Client:
    return httpx.Client(timeout=30.0, transport=_transport)


# ---- token store (rotation-aware) ----

def _load_tokens() -> dict:
    try:
        return json.loads(_token_path().read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _save_tokens(t: dict) -> None:
    p = _token_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(t))


def _store_token_response(d: dict) -> None:
    t = _load_tokens()
    t["access_token"] = d["access_token"]
    # Fortnox rotates the refresh token on every use — persist the new one.
    if d.get("refresh_token"):
        t["refresh_token"] = d["refresh_token"]
    t["expires_at"] = time.time() + int(d.get("expires_in", 3600))
    _save_tokens(t)


def is_connected() -> bool:
    return bool(_load_tokens().get("refresh_token"))


def configured() -> bool:
    return bool(client_id() and client_secret())


# ---- OAuth2 authorization code flow ----

def authorization_url(state: str) -> str:
    if not client_id():
        raise FortnoxAuthError("FORTNOX_CLIENT_ID not set")
    q = urlencode({
        "client_id": client_id(),
        "redirect_uri": redirect_uri(),
        "scope": scopes(),
        "state": state,
        "access_type": "offline",   # required to receive a refresh token
        "response_type": "code",
    })
    return f"{_auth_url()}?{q}"


def exchange_code(code: str) -> None:
    """Exchange the (10-minute) authorization code for tokens."""
    with _http() as c:
        r = c.post(_token_url(),
                   data={"grant_type": "authorization_code", "code": code,
                         "redirect_uri": redirect_uri()},
                   auth=(client_id(), client_secret()))
    if r.status_code >= 400:
        raise FortnoxError(f"token exchange failed: {r.status_code} {r.text}")
    _store_token_response(r.json())


def _refresh() -> None:
    rt = _load_tokens().get("refresh_token")
    if not rt:
        raise FortnoxAuthError("no refresh token — reconnect Fortnox")
    with _http() as c:
        r = c.post(_token_url(),
                   data={"grant_type": "refresh_token", "refresh_token": rt},
                   auth=(client_id(), client_secret()))
    if r.status_code >= 400:
        raise FortnoxAuthError(f"refresh failed: {r.status_code} {r.text}")
    _store_token_response(r.json())  # stores the ROTATED refresh token


def _access_token() -> str:
    t = _load_tokens()
    if not t.get("refresh_token"):
        raise FortnoxAuthError("Fortnox not connected")
    if t.get("expires_at", 0) - time.time() < 60:
        _refresh()
        t = _load_tokens()
    return t["access_token"]


# ---- API helper ----

def _api(method: str, path: str, _retry: bool = True, **kw) -> httpx.Response:
    headers = kw.pop("headers", {})
    headers.setdefault("Accept", "application/json")
    headers["Authorization"] = f"Bearer {_access_token()}"
    with _http() as c:
        r = c.request(method, f"{_api_base()}{path}", headers=headers, **kw)
    if r.status_code == 401 and _retry:
        _refresh()
        return _api(method, path, _retry=False, **kw)
    if r.status_code == 429:
        raise FortnoxTransient("rate limited (429) — backing off")
    if r.status_code >= 500:
        raise FortnoxTransient(f"Fortnox server error {r.status_code}")
    if r.status_code >= 400:
        raise FortnoxError(f"{method} {path} -> {r.status_code} {r.text[:300]}")
    return r


# ---- field mapping ----

def _amount(s: str) -> float:
    d = parse_amount(s or "")
    return float(d) if d is not None else 0.0


def _iso_date(s: str | None) -> str | None:
    if not s:
        return None
    parts = re.split(r"[./-]", s.strip())
    if len(parts) == 3 and len(parts[0]) == 2:  # dd.mm.yyyy -> yyyy-mm-dd
        d, m, y = parts
        return f"{y}-{m}-{d}"
    return s


def _resolve_supplier(payload: dict) -> str:
    """Fortnox needs an existing SupplierNumber. Resolve by organisation number
    from the VAT id, or fall back to a configured default. The supplier register
    is client-specific, so this is deliberately overridable."""
    default = os.environ.get("FORTNOX_DEFAULT_SUPPLIER")
    if default:
        return default
    orgnr = "".join(ch for ch in (payload.get("vat_number") or "") if ch.isdigit())
    if orgnr:
        r = _api("GET", f"/suppliers?organisationnumber={orgnr}")
        suppliers = (r.json().get("Suppliers") or [])
        if suppliers:
            return str(suppliers[0].get("SupplierNumber"))
    raise FortnoxError(
        f"no Fortnox supplier for VAT {payload.get('vat_number')!r}; "
        "create it in Fortnox or set FORTNOX_DEFAULT_SUPPLIER"
    )


def _upload_pdf(invoice_id: str) -> str:
    path = store.original_pdf_path(invoice_id)
    if not path.exists():
        raise FortnoxError("original PDF is missing")
    files = {"file": (path.name, path.read_bytes(), "application/pdf")}
    r = _api("POST", "/inbox?folderid=inbox_s", files=files)
    file_obj = r.json().get("File") or {}
    file_id = file_obj.get("Id") or file_obj.get("@id")
    if not file_id:
        raise FortnoxError(f"inbox upload returned no file id: {r.text[:200]}")
    return str(file_id)


def _create_supplier_invoice(payload: dict, supplier_number: str) -> str:
    account = int(os.environ.get("FORTNOX_DEFAULT_ACCOUNT", "4000"))
    rows = []
    for li in payload.get("allocation_lines", []):
        # Client-specific: a real chart of accounts would map each row to its
        # cost account; the row's project carries through to Fortnox Project.
        row = {"Account": account, "Total": _amount(li.get("amount"))}
        if li.get("project"):
            row["Project"] = li["project"]
        rows.append(row)

    inv = {
        "SupplierNumber": supplier_number,
        "InvoiceNumber": payload.get("invoice_number", ""),
        "InvoiceDate": _iso_date(payload.get("invoice_date")),
        "DueDate": _iso_date(payload.get("due_date")),
        "Currency": payload.get("currency") or "SEK",
        "Total": _amount(payload.get("total")),
        "VAT": _amount(payload.get("vat")),
        "SupplierInvoiceRows": rows,
    }
    if payload.get("payment_reference"):
        inv["OCR"] = payload["payment_reference"]

    r = _api("POST", "/supplierinvoices", json={"SupplierInvoice": inv})
    created = r.json().get("SupplierInvoice") or {}
    ref = created.get("GivenNumber") or created.get("DocumentNumber")
    if not ref:
        raise FortnoxError(f"create returned no invoice number: {r.text[:200]}")
    return str(ref)


def _link_file(file_id: str, given_number: str) -> None:
    body = {"SupplierInvoiceFileConnection":
            {"FileId": file_id, "SupplierInvoiceNumber": given_number}}
    _api("POST", "/supplierinvoicefileconnections", json=body)


def _load_ledger() -> dict:
    try:
        return json.loads(_ledger_path().read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _save_ledger(d: dict) -> None:
    p = _ledger_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d))


def deliver(payload: dict, idempotency_key: str, attempt: int) -> str:
    """Post a coded supplier invoice to Fortnox and return its Fortnox number.

    Fortnox has no native idempotency key, so we keep a local ledger keyed by the
    invoice fingerprint: a repeat delivery returns the existing number rather
    than creating a second invoice. (Residual risk: a crash between creating the
    invoice and writing the ledger — mitigate in production by writing the
    fortnox ref back inside the same outbox transaction.)
    """
    if not configured():
        raise FortnoxError("Fortnox not configured (set FORTNOX_CLIENT_ID / SECRET)")
    if not is_connected():
        raise FortnoxError("Fortnox not connected (authorize the integration first)")

    ledger = _load_ledger()
    if idempotency_key in ledger:
        return ledger[idempotency_key]

    supplier = _resolve_supplier(payload)
    file_id = _upload_pdf(payload["invoice_id"])
    ref = _create_supplier_invoice(payload, supplier)
    _link_file(file_id, ref)

    ledger[idempotency_key] = ref
    _save_ledger(ledger)
    log.info("delivered %s to Fortnox as supplier invoice %s", payload["invoice_id"], ref)
    return ref
