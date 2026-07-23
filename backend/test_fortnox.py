"""Offline tests for the Fortnox adapter, using a mocked HTTP transport.

    backend/.venv/bin/python test_fortnox.py

Validates the two things that break real integrations: refresh-token rotation
is persisted, and delivery is idempotent (no double-posting on retry).
"""

import json
import os
import time
from pathlib import Path

import httpx

os.environ["FORTNOX_CLIENT_ID"] = "cid"
os.environ["FORTNOX_CLIENT_SECRET"] = "csecret"
os.environ["FORTNOX_TOKEN_PATH"] = "/tmp/fnx_tokens.json"
os.environ["FORTNOX_LEDGER_PATH"] = "/tmp/fnx_ledger.json"

from app import fortnox, store  # noqa: E402

calls: dict[str, int] = {}


def handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    key = url.split("?")[0]
    calls[key] = calls.get(key, 0) + 1
    if url.startswith(fortnox.TOKEN_URL):
        return httpx.Response(200, json={"access_token": "AT_new",
                                         "refresh_token": "RT_new", "expires_in": 3600})
    if "/3/suppliers" in url:
        return httpx.Response(200, json={"Suppliers": [{"SupplierNumber": "42"}]})
    if key.endswith("/3/inbox"):
        return httpx.Response(200, json={"File": {"Id": "file-77"}})
    if key.endswith("/3/supplierinvoices"):
        return httpx.Response(200, json={"SupplierInvoice": {"GivenNumber": "1001"}})
    if "/3/supplierinvoicefileconnections" in url:
        return httpx.Response(200, json={"SupplierInvoiceFileConnection": {}})
    return httpx.Response(404, json={"error": "unhandled " + url})


fortnox._transport = httpx.MockTransport(handler)


def reset(tokens: dict):
    Path("/tmp/fnx_tokens.json").write_text(json.dumps(tokens))
    Path("/tmp/fnx_ledger.json").unlink(missing_ok=True)
    calls.clear()


def test_refresh_rotates_and_persists():
    reset({"access_token": "AT_old", "refresh_token": "RT_old",
           "expires_at": time.time() - 10})  # expired -> forces refresh
    token = fortnox._access_token()
    saved = json.loads(Path("/tmp/fnx_tokens.json").read_text())
    assert token == "AT_new", token
    assert saved["refresh_token"] == "RT_new", saved  # the rotated token was stored
    print("OK  refresh rotates and persists the new refresh token")


def test_deliver_is_idempotent():
    reset({"access_token": "AT", "refresh_token": "RT", "expires_at": time.time() + 3600})
    tid = "testfnx01"
    store.original_pdf_path(tid).parent.mkdir(parents=True, exist_ok=True)
    store.original_pdf_path(tid).write_bytes(b"%PDF-1.4 dummy %%EOF")
    payload = {
        "invoice_id": tid, "vat_number": "SE556677889901",
        "invoice_number": "X-1", "invoice_date": "14.07.2026", "due_date": "13.08.2026",
        "currency": "SEK", "total": "1.234,00", "vat": "246,80", "payment_reference": "123",
        "allocation_lines": [{"amount": "1.234,00", "project": "4412", "description": "x"}],
    }
    ref = fortnox.deliver(payload, tid, 1)
    assert ref == "1001", ref
    for ep in ["/3/suppliers", "/3/inbox", "/3/supplierinvoices",
               "/3/supplierinvoicefileconnections"]:
        assert any(k.endswith(ep) for k in calls), (ep, calls)
    creates = calls.get(fortnox.API_BASE + "/supplierinvoices", 0)

    ref2 = fortnox.deliver(payload, tid, 2)  # retry -> must not create again
    assert ref2 == "1001", ref2
    assert calls.get(fortnox.API_BASE + "/supplierinvoices", 0) == creates, calls
    print("OK  three-call delivery works and is idempotent on retry")

    # cleanup
    import shutil
    shutil.rmtree(store.original_pdf_path(tid).parent, ignore_errors=True)


if __name__ == "__main__":
    test_refresh_rotates_and_persists()
    test_deliver_is_idempotent()
    print("\nall fortnox adapter tests passed")
