"""Adapter to Marathon's supplier-invoice interface.

The real system would deliver through Marathon's API (preferred), a structured
import file, or Peppol - the route is confirmed with KASE. This mock stands in
for the API route and has the two properties that matter for a safe handover:

  * Idempotent - keyed by idempotency_key, so a retry can never post the same
    supplier invoice twice. A "ledger" file simulates Marathon remembering what
    it has already accepted.
  * Testable failure - set MARATHON_FAIL_ATTEMPTS=N to make the first N delivery
    attempts fail, to exercise the outbox's retry path.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

_LEDGER = Path(__file__).resolve().parent.parent / "data" / "marathon_ledger.json"


class MarathonError(Exception):
    """A transient delivery failure - the outbox should retry."""


def _load() -> dict:
    try:
        return json.loads(_LEDGER.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _save(d: dict) -> None:
    _LEDGER.parent.mkdir(parents=True, exist_ok=True)
    _LEDGER.write_text(json.dumps(d))


def deliver(payload: dict, idempotency_key: str, attempt: int) -> str:
    """Post a coded supplier invoice to Marathon and return its reference.

    Idempotent: a key already accepted returns its existing reference without
    posting again.
    """
    ledger = _load()
    if idempotency_key in ledger:
        return ledger[idempotency_key]  # already posted - do not post twice

    fail_attempts = int(os.environ.get("MARATHON_FAIL_ATTEMPTS", "0"))
    if attempt <= fail_attempts:
        raise MarathonError(
            f"Marathon interface unavailable (simulated failure, attempt {attempt})"
        )

    ref = "MAR-" + hashlib.sha256(idempotency_key.encode()).hexdigest()[:8].upper()
    ledger[idempotency_key] = ref
    _save(ledger)
    return ref
