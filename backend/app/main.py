"""FastAPI application - intake, extraction and verification API.

Two arrival paths feed the same pipeline (app/pipeline.py):
  * POST /api/invoices          browser upload
  * a watched folder            app/intake.py (started on app startup)

Endpoints:
  GET  /api/invoices            list processed invoices (the review queue)
  GET  /api/invoices/{id}       full result for the verification screen
  GET  /api/invoices/{id}/pages/{n}.png   rendered page image
  POST /api/invoices/{id}/verify          store the reviewer's confirmed values
  GET  /api/projects            Marathon projects (demo list)
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from . import intake, store
from .models import InvoiceResult
from .pipeline import PipelineError, process_pdf


@asynccontextmanager
async def lifespan(app: FastAPI):
    intake.start_background()  # begin watching the intake folder
    yield


app = FastAPI(title="Automated Invoice Capture", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev only; lock down before anything real
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


# Marathon is the single source of truth for projects; here we serve a small
# demo list. In the full system these are synchronised from Marathon and never
# typed by hand. Closed projects would be excluded from selection.
DEMO_PROJECTS = [
    {"code": "4412", "name": "Site A - Stockholm fit-out"},
    {"code": "4501", "name": "Site B - Goteborg warehouse"},
    {"code": "4720", "name": "Nordic distribution 2026"},
    {"code": "9000", "name": "Overhead - logistics"},
]


@app.get("/api/projects")
def projects() -> list[dict]:
    return DEMO_PROJECTS


@app.post("/api/invoices", response_model=InvoiceResult)
async def upload_invoice(file: UploadFile = File(...)) -> InvoiceResult:
    pdf_bytes = await file.read()
    # Run the (blocking) pipeline off the event loop.
    try:
        result, _duplicate = await run_in_threadpool(
            process_pdf, pdf_bytes, file.filename or "invoice.pdf"
        )
    except PipelineError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:  # surface auth/rate/model errors to the reviewer
        raise HTTPException(502, f"Extraction failed: {exc}") from exc
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

    # Persist the per-row project coding (the allocation lines).
    rows_by_index = {r["index"]: r for r in payload.get("line_items", [])}
    for it in result.get("line_items", []):
        if it["index"] in rows_by_index:
            it["project"] = rows_by_index[it["index"]].get("project", it.get("project", ""))

    result["verified"] = True
    store.save_result(invoice_id, result)
    return {"id": invoice_id, "verified": True}
