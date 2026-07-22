# Automated Invoice Capture — Mini Manual

A short guide to running the system and using the verification screen.

## Running it

Two processes: the backend (API + workers) and the frontend (web UI).

**Backend**

```
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

**Frontend**

```
cd frontend
npm install
npm run dev
```

Then open **http://localhost:5173**. The dev server proxies `/api` to the
backend on port 8000.

**Mock vs live reading.** With no API credential the backend runs in mock mode
(realistic sample data), so everything works offline. Set `ANTHROPIC_API_KEY`
(or sign in with the `ant` CLI) to switch to real extraction — no code change.

**Sample data.** To fill the queue with example invoices:

```
backend/.venv/bin/python make_samples.py 48
```

This drops 48 varied invoices into the intake folder; the intake worker ingests
them within a few seconds.

## Getting invoices in

Two ways, both feeding the same pipeline:

- **Watched folder** — drop a PDF into `backend/data/intake/incoming/`. Within a
  few seconds it is ingested and appears in the review queue. Processed
  originals move to `processed/`; duplicates to `duplicates/`; unreadable files
  to `failed/` (with a short `.error.txt`).
- **Upload** — click **Upload invoice (PDF)** in the top bar.

Only PDFs are accepted. The same invoice arriving twice is recognised by
fingerprint and not processed again.

## The review queue

The home screen is the **review queue**:

- **Search** — type a supplier, invoice number, or amount fragment.
- **Tabs** — All / To review / Verified.
- **Rows** — supplier, filename, total, a **⚠ N** badge if there are checks to
  look at, and the state (to review / verified / → Marathon).
- **Paging** — Prev / Next, 15 per page.

Click any row to open it. The queue refreshes automatically, so folder-dropped
invoices appear without reloading.

## The verification screen

The screen is split: the **invoice on the left** with coloured boxes, the
**editable form on the right**. They are linked both ways.

**What the colours mean**

| Colour | Meaning |
|---|---|
| Green | Read with high confidence, passed all checks |
| Amber | Low confidence, or a warning — please look |
| Red | Failed a check, or is contradictory |
| Grey (dashed) | Expected but not found on the page |
| Blue | The field you are working on now |

Colour is never the only signal — each state also has a distinct line weight and
dash pattern, so the screen stays usable under colour-vision deficiency.

**Binding**

- Click or Tab into a field → its box lights up on the invoice, the rest dim.
- Click a box on the invoice → the matching field is focused, ready to edit.

**Keyboard**

| Key | Action |
|---|---|
| Tab | Move to the next field |
| Enter | Confirm and advance |
| ⌘ / Ctrl + Enter | Approve the whole invoice |

**The signals panel** (top right) lists the checks: VAT and IBAN validity, the
payment-reference check digit, the net + VAT = total result, the supplier-vs-bank
country fraud check, and whether the line items sum to the net. Fix anything red
or amber before approving.

## Coding the line items

Below the fields is the **line-items table** — one row per printed line.

- Assign a **project** to each row from the dropdown (Marathon's projects).
- One invoice can be split across several projects — code each row separately.
- The header shows coding progress (e.g. "2/3 coded").
- The rows must sum exactly to the net total; a mismatch is flagged.

## Approving and handover to Marathon

Press **Approve** (or ⌘/Ctrl + Enter). This:

1. Records your confirmed values and coding in the audit trail (old → new, by
   whom, when).
2. Enqueues the invoice for delivery to Marathon.

You'll see the handover status by the button:

> **Verified ✓** · *Handing over to Marathon…* → **Delivered to Marathon · MAR-xxxxxxxx**

Back in the queue the invoice shows a **→ Marathon** badge. Delivery retries on
failure and can never post the same invoice twice.

## History (audit trail)

Every open invoice has a collapsible **History** panel showing what the system
read, every correction, the coding, verification, and the Marathon handover —
each with who and when. The trail is append-only and tamper-evident.

## Configuration (environment variables)

| Variable | Purpose | Default |
|---|---|---|
| `ANTHROPIC_API_KEY` | Enables real extraction (else mock) | unset (mock) |
| `INVOICE_CAPTURE_MOCK` | Force mock mode (`1`) | off |
| `INVOICE_CAPTURE_LIVE` | Force live mode (`1`) | off |
| `INVOICE_INTAKE_DIR` | Watched-folder location | `backend/data/intake` |
| `INVOICE_INTAKE_POLL` | Folder poll interval (seconds) | `5` |
| `INVOICE_INTAKE_ENABLED` | Turn the folder worker on/off | on |
| `INVOICE_MAX_PAGES` | Max pages sent to the model per invoice | `8` |
| `MARATHON_OUTBOX_ENABLED` | Turn the handover worker on/off | on |
| `MARATHON_OUTBOX_POLL` | Handover poll interval (seconds) | `3` |
| `MARATHON_FAIL_ATTEMPTS` | Simulate N failed handover attempts (testing) | `0` |
| `INVOICE_DB_PATH` | SQLite database file location | `backend/data/invoices.db` |

Keep the SQLite database on local disk — not a network share.

## API reference (for integrators)

| Endpoint | Purpose |
|---|---|
| `POST /api/invoices` | Upload a PDF |
| `GET /api/invoices?q=&status=&page=&page_size=` | The review queue (search + paging) |
| `GET /api/invoices/{id}` | Full result for the verification screen |
| `GET /api/invoices/{id}/pages/{n}.png` | A rendered page image |
| `POST /api/invoices/{id}/verify` | Save corrections + coding; enqueue handover |
| `GET /api/invoices/{id}/audit` | The audit trail |
| `GET /api/invoices/{id}/handover` | Marathon handover status |
| `GET /api/projects` | Marathon projects (demo list) |
| `GET /api/audit/integrity` | Recompute and verify the audit hash chain |

## Troubleshooting

- **Blank screen** — hard-reload the browser (Cmd/Ctrl + Shift + R).
- **"Extraction failed" on upload** — the API has no credit. Either add
  Developer Platform credit, or run in mock mode (unset the key / set
  `INVOICE_CAPTURE_MOCK=1`). A Claude subscription funds Claude Code, not the API.
- **Dropped file not appearing** — give it ~5–10s (it must settle first);
  check `data/intake/failed/` for a `.error.txt`.
- **Database errors** — ensure the SQLite file is on local disk, not a network
  share.
