"""A minimal filesystem + in-memory store.

This is intentionally simple for the first cut. The proposal's target is
PostgreSQL (typed columns + JSONB) with S3/MinIO object storage; this keeps the
same shape (an immutable original, rendered pages, and a JSON result) so the
swap is mechanical later.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

_INDEX: dict[str, dict] = {}


def _dir(invoice_id: str) -> Path:
    d = DATA_DIR / invoice_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def fingerprint(pdf_bytes: bytes) -> str:
    return hashlib.sha256(pdf_bytes).hexdigest()[:16]


def exists(invoice_id: str) -> bool:
    return invoice_id in _INDEX


def save_original(invoice_id: str, pdf_bytes: bytes) -> None:
    (_dir(invoice_id) / "original.pdf").write_bytes(pdf_bytes)


def save_page_image(invoice_id: str, page: int, image) -> None:
    image.save(_dir(invoice_id) / f"page_{page}.png", format="PNG")


def page_image_path(invoice_id: str, page: int) -> Path:
    return _dir(invoice_id) / f"page_{page}.png"


def save_result(invoice_id: str, result: dict) -> None:
    _INDEX[invoice_id] = result
    (_dir(invoice_id) / "result.json").write_text(json.dumps(result, indent=2))


def get_result(invoice_id: str) -> dict | None:
    if invoice_id in _INDEX:
        return _INDEX[invoice_id]
    path = _dir(invoice_id) / "result.json"
    if path.exists():
        result = json.loads(path.read_text())
        _INDEX[invoice_id] = result
        return result
    return None


def _summary(r: dict) -> dict:
    return {
        "id": r["id"],
        "filename": r["filename"],
        "verified": bool(r.get("verified", False)),
    }


def list_results() -> list[dict]:
    """The review queue - scans disk so it survives restarts, merged with
    anything held in memory."""
    out: dict[str, dict] = {}
    for d in sorted(DATA_DIR.iterdir()):
        f = d / "result.json"
        if d.is_dir() and f.exists():
            try:
                out[d.name] = _summary(json.loads(f.read_text()))
            except (json.JSONDecodeError, KeyError, OSError):
                continue
    for r in _INDEX.values():
        out[r["id"]] = _summary(r)
    return sorted(out.values(), key=lambda x: x["filename"])
