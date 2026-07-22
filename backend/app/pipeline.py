"""The one pipeline that turns PDF bytes into a stored, verified-ready result.

Both intake paths use this: the browser upload (main.py) and the watched-folder
worker (intake.py). Keeping it in one place means one code path to trust.

A process-wide lock serialises the mutation region so the folder worker and an
HTTP upload can't interleave writes to the store. At this volume (a handful of
invoices per minute) serialising is free and removes a class of race.
"""

from __future__ import annotations

import threading

from . import store
from .extraction import extract
from .models import InvoiceResult
from .pdf_utils import render_pdf
from .validation import build_fields

_lock = threading.Lock()


class PipelineError(Exception):
    """A problem with the input (bad or unreadable PDF) - a client error."""


def process_pdf(pdf_bytes: bytes, filename: str) -> tuple[InvoiceResult, bool]:
    """Render, extract, validate and store one invoice.

    Returns (result, is_duplicate). A duplicate is recognised by content
    fingerprint and returned unchanged rather than processed again.
    Raises PipelineError for bad input; extraction errors propagate.
    """
    if not pdf_bytes or not pdf_bytes.startswith(b"%PDF"):
        raise PipelineError("Only PDF files are supported.")

    invoice_id = store.fingerprint(pdf_bytes)

    with _lock:
        if store.exists(invoice_id):
            existing = store.get_result(invoice_id)
            if existing:
                return InvoiceResult(**existing), True

        store.save_original(invoice_id, pdf_bytes)

        pages = render_pdf(pdf_bytes)
        if not pages:
            raise PipelineError("Could not render any pages from the PDF.")
        for i, p in enumerate(pages):
            store.save_page_image(invoice_id, i, p.image)

        raw = extract(pages, fingerprint=invoice_id)  # may raise on auth/rate/model errors
        page_dims = [(p.width, p.height) for p in pages]
        fields, line_items, checks, signals = build_fields(raw, page_dims)

        result = InvoiceResult(
            id=invoice_id,
            filename=filename or "invoice.pdf",
            pages=[
                {
                    "page": i,
                    "width": p.width,
                    "height": p.height,
                    "image_url": f"/api/invoices/{invoice_id}/pages/{i}.png",
                }
                for i, p in enumerate(pages)
            ],
            fields=fields,
            line_items=line_items,
            checks=checks,
            signals=signals,
        )
        store.save_result(invoice_id, result.model_dump())
        return result, False
