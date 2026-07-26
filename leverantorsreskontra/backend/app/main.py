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
from fastapi.responses import FileResponse, Response

import os
import secrets
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from . import (bas, db, dimensioner, fortnox, intake, kontering, moms, outbox,
               pain, sie, store, validation)
from .models import InvoiceResult
from .pipeline import PipelineError, process_pdf


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()                   # ensure the SQLite schema exists
    intake.start_background()   # begin watching the intake folder
    outbox.start_background()   # begin delivering verified invoices to Marathon
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


# ---- BAS + moms kontering (Milstolpe 1) ----

def _dec(x) -> Decimal:
    """Tolka ett belopp (accepterar '1 234,56', '1234.56', tal)."""
    if x is None or x == "":
        raise ValueError("belopp saknas")
    d = validation.parse_amount(str(x))
    if d is None:
        try:
            d = Decimal(str(x))
        except InvalidOperation:
            raise ValueError(f"ogiltigt belopp: {x!r}")
    return d


@app.get("/api/bas/konton")
def bas_konton() -> list[dict]:
    """Kostnadskonton valbara för radkontering (UI-dropdown)."""
    return [{"nummer": k.nummer, "namn": k.namn} for k in bas.kostnadskonton()]


@app.get("/api/moms/koder")
def moms_koder() -> list[dict]:
    return [{"kod": m.kod, "beskrivning": m.beskrivning,
             "sats": str(m.sats), "omvand": m.omvand}
            for m in moms.MOMSKODER.values()]


@app.get("/api/kostnadsstallen")
def kostnadsstallen() -> list[dict]:
    """Kostnadsställen (dimension 1) för radkontering."""
    return dimensioner.kostnadsstallen()


@app.post("/api/kontering/forslag")
def kontering_forslag(payload: dict) -> dict:
    """Bygg ett balanserat verifikat av konterade rader.

    Body: {"rader": [{"konto","netto","momskod","beskrivning"}], "angivet_total"?}
    """
    rader_in = payload.get("rader") or []
    if not rader_in:
        raise HTTPException(status_code=400, detail="inga konteringsrader")
    try:
        rader = [
            kontering.Konteringsrad(
                konto=str(r["konto"]),
                netto=_dec(r.get("netto")),
                momskod=str(r.get("momskod") or moms.DEFAULT_MOMSKOD),
                beskrivning=str(r.get("beskrivning") or ""),
                kostnadsstalle=str(r.get("kostnadsstalle") or ""))
            for r in rader_in
        ]
        total = payload.get("angivet_total")
        ver = kontering.bygg_verifikat(
            rader, _dec(total) if total not in (None, "") else None)
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return kontering.som_dict(ver)


# ---- SIE4-export (Milstolpe 2) ----

def _sie_response(fakturor: list[dict], filename: str) -> Response:
    text = sie.bygg_sie(
        fakturor,
        fnamn=os.environ.get("SIE_FNAMN", "Företaget AB"),
        orgnr=os.environ.get("SIE_ORGNR", "556000-0000"),
        sign=os.environ.get("SIE_SIGN", "LR"),
        serie=os.environ.get("SIE_SERIE", "A"),
    )
    return Response(
        content=sie.till_bytes(text),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/sie/export")
def sie_export():
    """SIE4-fil med alla konterade verifikat (för import i bokföringssystemet)."""
    fakturor = store.verifikat_for_export()
    if not fakturor:
        raise HTTPException(status_code=404, detail="inga attesterade verifikat att exportera")
    return _sie_response(fakturor, "leverantorsreskontra.sie")


@app.get("/api/invoices/{invoice_id}/sie")
def sie_export_invoice(invoice_id: str):
    """SIE4-fil för en enskild faktura."""
    fakturor = store.verifikat_for_export(invoice_id)
    if not fakturor:
        raise HTTPException(status_code=404, detail="fakturan saknar konterat verifikat")
    return _sie_response(fakturor, f"{invoice_id}.sie")


# ---- ISO 20022 pain.001 betalfil (Milstolpe 2) ----

def _pain_response(betalningar: list[dict], filename: str) -> Response:
    now = datetime.now()
    try:
        xml, hoppade = pain.bygg_pain001(
            betalningar,
            msg_id=pain.ny_msg_id(now),
            cre_dttm=now.strftime("%Y-%m-%dT%H:%M:%S"),
            initg_nm=os.environ.get("PAIN_INITG_NM", os.environ.get("SIE_FNAMN", "Företaget AB")),
            dbtr_nm=os.environ.get("PAIN_DBTR_NM", os.environ.get("SIE_FNAMN", "Företaget AB")),
            dbtr_iban=os.environ.get("PAIN_DBTR_IBAN", ""),
            dbtr_bic=os.environ.get("PAIN_DBTR_BIC", ""),
            exctn_fallback=now.strftime("%Y-%m-%d"),
        )
    except pain.PainError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return Response(
        content=xml.encode("utf-8"),
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"',
                 "X-Skipped-No-Iban": str(len(hoppade))},
    )


@app.get("/api/pain/export")
def pain_export():
    """pain.001-betalfil för alla attesterade fakturor med konto + belopp."""
    return _pain_response(store.betalunderlag(), "leverantorsreskontra-pain001.xml")


@app.get("/api/invoices/{invoice_id}/pain")
def pain_export_invoice(invoice_id: str):
    """pain.001-betalfil för en enskild faktura (kräver attesterad)."""
    underlag = store.betalunderlag(invoice_id)
    if not underlag:
        raise HTTPException(status_code=404,
                            detail="fakturan är inte attesterad eller saknar verifikat")
    return _pain_response(underlag, f"{invoice_id}-pain001.xml")


# ---- Attestflöde (Milstolpe 3) ----

def _beloppsgrans() -> Decimal | None:
    raw = os.environ.get("ATTEST_BELOPPSGRANS")
    return Decimal(raw) if raw else None


@app.post("/api/invoices/{invoice_id}/attestera")
def attestera(invoice_id: str, payload: dict) -> dict:
    """Attestera en granskad faktura (attestant ≠ granskare, inom beloppsgräns)."""
    attestant = payload.get("attestant") or ""
    try:
        updated = store.attestera(invoice_id, attestant,
                                  actor=attestant or "attestant",
                                  beloppsgrans=_beloppsgrans())
    except store.AttestError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if updated is None:
        raise HTTPException(404, "Invoice not found.")
    return {"id": invoice_id, "attest_status": updated["attest_status"],
            "attestant": updated["attestant"]}


@app.post("/api/invoices/{invoice_id}/avvisa")
def avvisa(invoice_id: str, payload: dict) -> dict:
    """Avvisa en faktura (tillbaka för omkontering)."""
    updated = store.avvisa(invoice_id, actor=payload.get("reviewer") or "granskare",
                           kommentar=payload.get("kommentar", ""))
    if updated is None:
        raise HTTPException(404, "Invoice not found.")
    return {"id": invoice_id, "attest_status": updated["attest_status"]}


_TARGET_LABELS = {"marathon": "Marathon", "fortnox": "Fortnox",
                  "accounts_payable": "Accounts Payable"}


@app.get("/api/config")
def config() -> dict:
    """Front-end configuration — notably the active handover destination, so the
    UI can label it correctly."""
    target = store_env_target()
    return {
        "handover_target": target,
        "handover_label": _TARGET_LABELS.get(target, target.capitalize()),
    }


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
def list_invoices(q: str = "", status: str = "all",
                  page: int = 1, page_size: int = 15) -> dict:
    """The review queue, searchable and paged.

    Query params: q (search), status (all|todo|done), page, page_size.
    """
    return store.query_invoices(q=q, status=status, page=page, page_size=page_size)


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
    """Persist the reviewer's confirmed values and coding.

    Every changed value is recorded in the audit trail (old -> new, by whom,
    when). In the full system this is also where the coded invoice would be
    handed to Marathon via the transactional outbox.
    """
    actor = payload.get("reviewer") or "reviewer"
    field_values = {f["key"]: f.get("value", "") for f in payload.get("fields", [])}
    projects = {r["index"]: r.get("project", "") for r in payload.get("line_items", [])}
    codings = {r["index"]: {"konto": r.get("konto", ""), "momskod": r.get("momskod", ""),
                            "kostnadsstalle": r.get("kostnadsstalle", "")}
               for r in payload.get("line_items", [])}

    updated = store.verify_invoice(invoice_id, field_values, projects, actor,
                                   codings=codings)
    if updated is None:
        raise HTTPException(404, "Invoice not found.")
    return {"id": invoice_id, "verified": True}


@app.get("/api/invoices/{invoice_id}/audit")
def invoice_audit(invoice_id: str) -> list[dict]:
    if not store.exists(invoice_id):
        raise HTTPException(404, "Invoice not found.")
    return store.get_audit(invoice_id)


@app.get("/api/invoices/{invoice_id}/handover")
def invoice_handover(invoice_id: str) -> dict:
    """Marathon handover status for one invoice."""
    if not store.exists(invoice_id):
        raise HTTPException(404, "Invoice not found.")
    return store.get_handover(invoice_id)


@app.get("/api/audit/integrity")
def audit_integrity() -> dict:
    """Recompute the audit hash chain and report whether it is intact."""
    return store.audit_integrity()


# ---- Fortnox OAuth2 connection (used when HANDOVER_TARGET=fortnox) ----

@app.get("/api/fortnox/status")
def fortnox_status() -> dict:
    return {
        "target": store_env_target(),
        "configured": fortnox.configured(),
        "connected": fortnox.is_connected(),
    }


def store_env_target() -> str:
    import os
    return os.environ.get("HANDOVER_TARGET", "marathon").lower()


@app.get("/api/fortnox/connect")
def fortnox_connect() -> dict:
    """Return the Fortnox authorization URL for the customer to approve."""
    try:
        return {"authorization_url": fortnox.authorization_url(secrets.token_urlsafe(8))}
    except fortnox.FortnoxAuthError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/fortnox/callback")
def fortnox_callback(code: str, state: str = "") -> dict:
    """OAuth redirect target: exchange the code for tokens."""
    try:
        fortnox.exchange_code(code)
    except (fortnox.FortnoxError, fortnox.FortnoxAuthError) as e:
        raise HTTPException(400, str(e)) from e
    return {"connected": True}
