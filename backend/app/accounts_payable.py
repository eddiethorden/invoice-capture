"""Handover adapter to the Accounts Payable module.

Delivers each approved invoice to the AP module's intake API, which is modelled
on Fortnox's "create custom document" endpoint: the invoice is posted as an
INBOUND custom document under a fixed referenceType. Selected with
HANDOVER_TARGET=accounts_payable.

Like the other adapters it exposes deliver(payload, idempotency_key, attempt).
Idempotency is carried end-to-end: the idempotency_key (the invoice fingerprint)
is sent as the custom document's externalId, so a retry updates the same payable
rather than creating a second one, and the AP module reports created=0.
"""

from __future__ import annotations

import logging
import os

import httpx

log = logging.getLogger("invoice.accounts_payable")

# Where the AP module's intake API lives, and the custom-document type we post
# under. The referenceType must satisfy Fortnox's rule ([a-zA-Z0-9_-], 1..25,
# not a reserved type) — the AP module validates it and rejects violations.
INTAKE_URL = "http://localhost:8010/ap/custom-documents"
REFERENCE_TYPE = "KASE_CAPTURE"


def _intake_url() -> str:
    return os.environ.get("AP_INTAKE_URL", INTAKE_URL)


def _reference_type() -> str:
    return os.environ.get("AP_REFERENCE_TYPE", REFERENCE_TYPE)


class AccountsPayableError(Exception):
    """Permanent delivery failure — the outbox should stop retrying."""


class AccountsPayableTransient(Exception):
    """Transient failure (AP module down, timeout, 5xx) — retry."""


def deliver(payload: dict, idempotency_key: str, attempt: int) -> str:
    """Post the coded invoice to the AP module and return its payable reference."""
    body = {
        "category": "INBOUND",
        "referenceType": _reference_type(),
        "externalId": idempotency_key,
        "document": payload,
    }
    try:
        with httpx.Client(timeout=10.0) as c:
            r = c.post(_intake_url(), json=body)
    except httpx.HTTPError as e:
        raise AccountsPayableTransient(f"AP module unreachable: {e}") from e

    if r.status_code >= 500:
        raise AccountsPayableTransient(f"AP module error {r.status_code}")
    if r.status_code >= 400:
        # 400 referenceTypeNotAllowed / bad request — a config bug, not transient.
        raise AccountsPayableError(f"AP intake rejected the document: "
                                   f"{r.status_code} {r.text[:200]}")

    data = r.json()
    ref = data.get("reference")
    if not ref:
        raise AccountsPayableError(f"AP intake returned no reference: {r.text[:200]}")
    log.info("delivered %s to AP as payable %s (created=%s)",
             payload.get("invoice_id"), ref, data.get("created"))
    return str(ref)
