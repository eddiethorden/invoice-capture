"""SQLite connection management and schema.

SQLite is the working store (Marathon remains the system of record). Settings
follow the recommendation memo: WAL for concurrent readers, foreign keys on,
a busy timeout so brief writer contention just waits, and STRICT tables for
rigid typing. The DB file must live on local disk, never a network share.

A connection is opened per operation (cheap at this volume) so there are no
cross-thread sharing concerns between the HTTP handlers and the intake worker.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def db_path() -> Path:
    return Path(os.environ.get("INVOICE_DB_PATH", _DATA_DIR / "invoices.db"))


SCHEMA = """
CREATE TABLE IF NOT EXISTS invoices (
    id           TEXT PRIMARY KEY,
    filename     TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    verified     INTEGER NOT NULL DEFAULT 0,
    verified_at  TEXT,
    verified_by  TEXT,
    pages_json   TEXT NOT NULL,
    checks_json  TEXT NOT NULL,
    signals_json TEXT NOT NULL,
    -- denormalised summary + search, populated at ingest for a fast queue
    supplier     TEXT NOT NULL DEFAULT '',
    total        TEXT NOT NULL DEFAULT '',
    currency     TEXT NOT NULL DEFAULT '',
    issues       INTEGER NOT NULL DEFAULT 0,
    search_text  TEXT NOT NULL DEFAULT '',
    -- handover to Marathon
    handover_status TEXT NOT NULL DEFAULT 'none',  -- none|pending|delivered|failed
    marathon_ref    TEXT
) STRICT;

CREATE INDEX IF NOT EXISTS ix_invoices_created ON invoices(created_at DESC);

-- Transactional outbox: a handover row is written in the same transaction that
-- verifies an invoice, then delivered by a separate worker. The idempotency_key
-- is UNIQUE so an invoice can only ever be enqueued (and posted) once.
CREATE TABLE IF NOT EXISTS outbox (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id      TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    status          TEXT NOT NULL DEFAULT 'pending',  -- pending|delivered|failed
    attempts        INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TEXT,
    last_error      TEXT,
    marathon_ref    TEXT,
    payload_json    TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    delivered_at    TEXT
) STRICT;

CREATE INDEX IF NOT EXISTS ix_outbox_pending ON outbox(status, next_attempt_at);

CREATE TABLE IF NOT EXISTS fields (
    invoice_id TEXT NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    key        TEXT NOT NULL,
    label      TEXT NOT NULL,
    value      TEXT NOT NULL,
    confidence REAL NOT NULL,
    found      INTEGER NOT NULL,
    page       INTEGER NOT NULL,
    status     TEXT NOT NULL,
    box_json   TEXT,
    PRIMARY KEY (invoice_id, key)
) STRICT;

CREATE TABLE IF NOT EXISTS line_items (
    invoice_id  TEXT NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    idx         INTEGER NOT NULL,
    description TEXT NOT NULL,
    quantity    TEXT NOT NULL,
    unit_price  TEXT NOT NULL,
    amount      TEXT NOT NULL,
    confidence  REAL NOT NULL,
    page        INTEGER NOT NULL,
    status      TEXT NOT NULL,
    box_json    TEXT,
    project     TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (invoice_id, idx)
) STRICT;

-- Append-only audit log. Not FK-linked to invoices, so the trail survives even
-- if an invoice row is later purged. A global hash chain makes it tamper-evident:
-- row_hash = sha256(prev_hash + this row), so altering or deleting any row breaks
-- every hash after it.
CREATE TABLE IF NOT EXISTS audit (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id TEXT NOT NULL,
    ts         TEXT NOT NULL,
    actor      TEXT NOT NULL,
    action     TEXT NOT NULL,
    field_key  TEXT,
    old_value  TEXT,
    new_value  TEXT,
    note       TEXT,
    prev_hash  TEXT NOT NULL,
    row_hash   TEXT NOT NULL
) STRICT;

CREATE INDEX IF NOT EXISTS ix_audit_invoice ON audit(invoice_id, seq);
"""

_init_lock = threading.Lock()
_initialized = False


@contextmanager
def connect():
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init() -> None:
    global _initialized
    if _initialized:
        return
    with _init_lock:
        if _initialized:
            return
        with connect() as c:
            c.executescript(SCHEMA)
            _migrate(c)
        _initialized = True


# Forward-safe column additions for databases created before the summary/search
# columns existed. STRICT tables allow ADD COLUMN with a constant default.
_INVOICE_COLUMNS = [
    ("supplier", "TEXT NOT NULL DEFAULT ''"),
    ("total", "TEXT NOT NULL DEFAULT ''"),
    ("currency", "TEXT NOT NULL DEFAULT ''"),
    ("issues", "INTEGER NOT NULL DEFAULT 0"),
    ("search_text", "TEXT NOT NULL DEFAULT ''"),
    ("handover_status", "TEXT NOT NULL DEFAULT 'none'"),
    ("marathon_ref", "TEXT"),
]


def _migrate(c) -> None:
    have = {r["name"] for r in c.execute("PRAGMA table_info(invoices)")}
    for name, decl in _INVOICE_COLUMNS:
        if name not in have:
            c.execute(f"ALTER TABLE invoices ADD COLUMN {name} {decl}")
