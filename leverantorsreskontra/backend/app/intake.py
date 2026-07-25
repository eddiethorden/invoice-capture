"""Stage 1 - arrival via a watched folder.

Drop a PDF into <intake>/incoming and it is ingested into the store. The folder
is a queue, not a database: once processed the original is moved out of the way.

    incoming/     drop here
    processing/   claimed, being read (atomic rename in)
    processed/    ingested OK
    duplicates/   recognised by fingerprint, not reprocessed
    failed/       bad PDF or extraction error, with a .error.txt beside it

Detection is by polling (default every 5s) - robust over network shares, where
OS file-change events are unreliable. Two hazards are handled explicitly:
partial writes (a file is only touched once its size has settled and it looks
like a complete PDF) and double-processing (an atomic rename claims the file).
"""

from __future__ import annotations

import logging
import os
import shutil
import threading
import time
from pathlib import Path

from .pipeline import PipelineError, process_pdf

log = logging.getLogger("invoice.intake")

SUBDIRS = ("incoming", "processing", "processed", "duplicates", "failed")
POLL_SECONDS = float(os.environ.get("INVOICE_INTAKE_POLL", "5"))


def base_dir() -> Path:
    default = Path(__file__).resolve().parent.parent / "data" / "intake"
    return Path(os.environ.get("INVOICE_INTAKE_DIR", default))


def ensure_dirs(base: Path) -> None:
    for s in SUBDIRS:
        (base / s).mkdir(parents=True, exist_ok=True)


def _unique(target: Path) -> Path:
    if not target.exists():
        return target
    i = 1
    while True:
        cand = target.with_name(f"{target.stem}__{i}{target.suffix}")
        if not cand.exists():
            return cand
        i += 1


def _move(src: Path, dst_dir: Path, name: str, note: str | None = None) -> None:
    dst = _unique(dst_dir / name)
    try:
        src.rename(dst)
    except OSError:  # e.g. cross-device move
        shutil.move(str(src), str(dst))
    if note:
        dst.with_name(dst.name + ".error.txt").write_text(note)


def _looks_like_complete_pdf(path: Path) -> bool:
    try:
        size = path.stat().st_size
        with open(path, "rb") as f:
            head = f.read(5)
            f.seek(max(0, size - 1024))
            tail = f.read()
    except OSError:
        return False
    return head.startswith(b"%PDF") and b"%%EOF" in tail


def _process_claimed(base: Path, path: Path) -> None:
    """`path` is already inside processing/ and owned by us."""
    name = path.name
    if not _looks_like_complete_pdf(path):
        _move(path, base / "failed", name, "not a valid or complete PDF")
        log.warning("failed (not a valid PDF): %s", name)
        return
    try:
        result, duplicate = process_pdf(path.read_bytes(), name)
    except PipelineError as e:
        _move(path, base / "failed", name, str(e))
        log.warning("failed (%s): %s", e, name)
        return
    except Exception as e:  # extraction / auth / rate errors
        _move(path, base / "failed", name, f"extraction failed: {e}")
        log.exception("failed (extraction) : %s", name)
        return

    if duplicate:
        _move(path, base / "duplicates", name, f"duplicate of {result.id}")
        log.info("duplicate: %s (already stored as %s)", name, result.id)
    else:
        _move(path, base / "processed", name)
        log.info(
            "ingested: %s -> %s (%d fields, %d line items)",
            name, result.id, len(result.fields), len(result.line_items),
        )


def _poll_once(base: Path, seen_size: dict[str, int]) -> None:
    incoming = base / "incoming"
    files = sorted(
        (p for p in incoming.iterdir()
         if p.is_file() and p.suffix.lower() == ".pdf"),
        key=lambda p: p.stat().st_mtime,
    )
    for path in files:
        try:
            size = path.stat().st_size
        except OSError:
            continue
        # Settle check: only act once the size is unchanged across two polls.
        if seen_size.get(path.name) != size:
            seen_size[path.name] = size
            continue
        seen_size.pop(path.name, None)
        # Claim by atomic rename into processing/.
        claimed = _unique(base / "processing" / path.name)
        try:
            path.rename(claimed)
        except OSError:
            continue  # someone else took it, or it vanished
        _process_claimed(base, claimed)


def run_poller(stop: threading.Event | None = None) -> None:
    base = base_dir()
    ensure_dirs(base)
    log.info("intake watching %s (poll %.0fs)", base / "incoming", POLL_SECONDS)
    seen_size: dict[str, int] = {}
    while stop is None or not stop.is_set():
        try:
            _poll_once(base, seen_size)
        except Exception:
            log.exception("intake poll cycle error")
        time.sleep(POLL_SECONDS)


def start_background() -> threading.Thread | None:
    if os.environ.get("INVOICE_INTAKE_ENABLED", "1") != "1":
        log.info("intake disabled (INVOICE_INTAKE_ENABLED != 1)")
        return None
    t = threading.Thread(target=run_poller, name="intake-poller", daemon=True)
    t.start()
    return t
