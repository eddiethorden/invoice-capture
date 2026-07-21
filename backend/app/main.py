"""FastAPI application - the intake, extraction and verification API.

Endpoints mirror the pipeline stages:
  POST /api/invoices            upload -> render -> extract -> validate
  GET  /api/invoices            list processed invoices
  GET  /api/invoices/{id}       full result for the verification screen
  GET  /api/invoices/{id}/pages/{n}.png   rendered page image
  POST /api/invoices/{id}/verify          store the reviewer's confirmed values
"""

from __future__ import annotations

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from . import store
from .extraction import extract
from .models import InvoiceResult
from .pdf_utils import render_pdf
from .validation import build_fields

app = FastAPI(title="Automated Invoice Capture", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev only; lock down before anything real
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/invoices", response_model=InvoiceResult)
async def upload_invoice(file: UploadFile = File(...)) -> InvoiceResult:
    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(400, "Empty file.")
    if not pdf_bytes.startswith(b"%PDF"):
        raise HTTPException(400, "Only PDF files are supported.")

    invoice_id = store.fingerprint(pdf_bytes)
    if store.exists(invoice_id):
        # Stage 1 - duplicate detection: recognised rather than re-processed.
        existing = store.get_result(invoice_id)
        if existing:
            return InvoiceResult(**existing)

    store.save_original(invoice_id, pdf_bytes)

    pages = render_pdf(pdf_bytes)
    if not pages:
        raise HTTPException(422, "Could not render any pages from the PDF.")

    for i, p in enumerate(pages):
        store.save_page_image(invoice_id, i, p.image)

    try:
        raw = extract(pages)
    except Exception as exc:  # surface auth/rate/model errors to the reviewer
        raise HTTPException(502, f"Extraction failed: {exc}") from exc
    page_dims = [(p.width, p.height) for p in pages]
    fields, checks, signals = build_fields(raw, page_dims)

    result = InvoiceResult(
        id=invoice_id,
        filename=file.filename or "invoice.pdf",
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
        checks=checks,
        signals=signals,
    )
    store.save_result(invoice_id, result.model_dump())
    return result


@app.get("/api/invoices")
def list_invoices() -> list[dict]:
    return store.list_results()


@app.get("/api/invoices/{invoice_id}", response_model=InvoiceResult)
def get_invoice(invoice_id: str) -> InvoiceResult:
    result = store.get_result(invoice_id)
    if not result:
        raise HTTPException(404, "Invoice not found.")
    return InvoiceResult(**result)


@app.get("/api/invoices/{invoice_id}/pages/{page}.png")
def get_page_image(invoice_id: str, page: int):
    path = store.page_image_path(invoice_id, page)
    if not path.exists():
        raise HTTPException(404, "Page image not found.")
    return FileResponse(path, media_type="image/png")


@app.post("/api/invoices/{invoice_id}/verify")
def verify_invoice(invoice_id: str, payload: dict) -> dict:
    """Persist the reviewer's confirmed values.

    In the full system this is the point at which the coded invoice is handed
    over to Marathon via the transactional outbox. For now we store the
    confirmed values and mark the invoice verified.
    """
    result = store.get_result(invoice_id)
    if not result:
        raise HTTPException(404, "Invoice not found.")
    confirmed = payload.get("fields", [])
    by_key = {f["key"]: f for f in confirmed}
    for f in result["fields"]:
        if f["key"] in by_key:
            f["value"] = by_key[f["key"]].get("value", f["value"])
            f["status"] = "green"
    result["verified"] = True
    store.save_result(invoice_id, result)
    return {"id": invoice_id, "verified": True}
