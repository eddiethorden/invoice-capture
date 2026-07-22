"""Stage 6 - handover to Marathon.

A background worker that drains the transactional outbox: for each pending row
it calls the Marathon adapter and, on success, stores the returned reference and
marks the invoice delivered; on failure it records the error and backs off,
giving up (status 'failed') after MAX_HANDOVER_ATTEMPTS. Delivery is idempotent
(keyed by the invoice fingerprint) so a retry can never post the same supplier
invoice twice.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time

from . import marathon, store

log = logging.getLogger("invoice.outbox")

POLL_SECONDS = float(os.environ.get("MARATHON_OUTBOX_POLL", "3"))


def _process_once() -> None:
    for row in store.due_outbox():
        attempt = row["attempts"] + 1
        try:
            ref = marathon.deliver(
                json.loads(row["payload_json"]), row["idempotency_key"], attempt
            )
            store.mark_delivered(row["id"], row["invoice_id"], ref, attempt)
            log.info("handed over %s -> %s", row["invoice_id"], ref)
        except Exception as e:
            store.mark_failed(row["id"], row["invoice_id"], attempt, str(e))
            log.warning("handover attempt %d failed for %s: %s",
                        attempt, row["invoice_id"], e)


def run_poller(stop: threading.Event | None = None) -> None:
    log.info("outbox worker started (poll %.0fs)", POLL_SECONDS)
    while stop is None or not stop.is_set():
        try:
            _process_once()
        except Exception:
            log.exception("outbox poll cycle error")
        time.sleep(POLL_SECONDS)


def start_background() -> threading.Thread | None:
    if os.environ.get("MARATHON_OUTBOX_ENABLED", "1") != "1":
        log.info("outbox worker disabled (MARATHON_OUTBOX_ENABLED != 1)")
        return None
    t = threading.Thread(target=run_poller, name="outbox-worker", daemon=True)
    t.start()
    return t
