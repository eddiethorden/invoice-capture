# Automated Invoice Capture

Reads incoming supplier invoices, presents every extracted value visually
marked on the invoice for a human to confirm, and prepares fully coded cost
data for delivery into Marathon.

This repository is the first working slice of the proposal in
`Invoice Capture Proposal`: **extraction + the verification screen**, with a
**vision-LLM-first** reading engine (Claude Opus 4.8).

```
PDF ─▶ render pages ─▶ Claude vision (fields + confidence + boxes)
    ─▶ arithmetic/structural checks ─▶ split-screen verification UI
```

## What works today

- Upload a PDF invoice (email / folder intake come later).
- Pages are rendered and each field is read with a **confidence** and a
  **bounding box** that maps 1:1 to the page.
- The verification screen shows the invoice on the left with colour-coded,
  keyboard-navigable boxes bound to an editable form on the right.
- Net + VAT = Total and other checks flag problems before the reviewer looks.
- Locale-aware number parsing (`1.234,56` vs `1,234.56` vs `1 234,56`).
- **Per-country validation**: structural VAT and IBAN checks, payment-reference
  check digit, and a supplier-country vs bank-country **fraud mismatch** signal
  (python-stdnum). Invalid identifiers escalate the field to red/amber.

Runs with **no API key** using a built-in mock invoice, so you can see the UI
immediately; set `ANTHROPIC_API_KEY` for real extraction.

## Run it

### Backend (FastAPI)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# optional, for real extraction:
export ANTHROPIC_API_KEY=sk-ant-...
uvicorn app.main:app --reload --port 8000
```

### Frontend (Vite + React)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 and upload a PDF. The dev server proxies `/api` to
the backend on port 8000.

## Layout

```
backend/app/
  main.py         FastAPI endpoints (intake, result, page images, verify)
  pdf_utils.py    PDF -> page images (pypdfium2)
  extraction.py   Claude vision extraction + mock fallback
  validation.py   number parsing, net+VAT check, per-field status
  models.py       Pydantic schemas (raw extraction + API response)
  fields.py       the canonical field set (maps to Marathon dimensions)
  store.py        filesystem + in-memory store (Postgres/S3 later)
frontend/src/
  App.jsx                     upload + state + keyboard flow
  components/InvoiceViewer.jsx invoice image + SVG box overlay
  components/FieldForm.jsx     editable, bound field form
```

## Next steps (from the proposal, not yet built)

- Coding against Marathon's dimensions and the transactional-outbox handover.
- Online VIES lookup (confirm a VAT number is *registered*, not just valid);
  reverse-charge recognition; currency conversion with rate + rate date.
- Layout-fingerprint cache so seen suppliers are read deterministically.
- PostgreSQL + object storage; PDF.js overlay; duplicate/audit trail.

Done: structural per-country validation (VAT / IBAN / check digit / fraud
mismatch) via python-stdnum.
