# Automated Invoice Capture — System Description

## What it is

A system that reads incoming supplier invoices, presents every extracted value
visually marked on the invoice for a person to confirm, codes each cost against
Marathon's dimensions, and delivers the verified, coded invoice into Marathon.

The core principle is deliberate: **the software proposes, a person verifies.**
It never posts a cost on its own. Every value it reads is drawn as a coloured
box on the invoice so the reviewer can see at a glance where each number came
from and confirm or correct it in seconds.

Marathon remains the system of record. This system is the step between an
invoice arriving and a correctly coded preliminary entry existing in Marathon.

## The pipeline — six stages

| Stage | What happens | Status |
|---|---|---|
| 1 · Arrival | Invoices arrive by watched folder or browser upload; a permanent copy is fingerprinted (SHA-256); duplicates are recognised, not reprocessed. | Built |
| 2 · Reading | Each page is rendered to an image and read by a vision model (or a built-in mock). | Built |
| 3 · Interpretation | Fields are identified with a confidence score and a bounding box tied to the exact words on the page. | Built |
| 4 · Verification | A person confirms or corrects on a split screen; arithmetic and per-country checks flag problems first. | Built |
| 5 · Coding | Each invoice row is coded to a Marathon project; the rows must sum to the net. | Built |
| 6 · Handover | The verified, coded invoice is delivered to Marathon reliably and once only. | Built |

Plus: a SQLite store with an append-only, tamper-evident audit trail, and a
searchable, paged review queue.

## How it works, stage by stage

**Arrival.** A background worker polls a watched folder every few seconds
(robust over network shares, where file-change events are unreliable). A file is
only picked up once its size has settled and it looks like a complete PDF, then
it is claimed by an atomic rename. Files move through a visible state machine:
`incoming → processing → processed`, with `duplicates` and `failed` (each failure
carries a short `.error.txt`). The browser upload feeds the same pipeline.

**Reading & interpretation.** Pages are rendered with pypdfium2. A vision model
(Claude Opus 4.8) reads each page and returns the fields — supplier, invoice
number, dates, net/VAT/total, currency, VAT number, IBAN, payment reference,
purchase order — each with a confidence and a bounding box. Boxes are stored
normalised (0–1) so they stay aligned at any display size. When no API
credential is present the system runs in **mock mode** with realistic sample
data, so the whole application is usable offline.

**Verification.** The screen is split: the invoice on the left with colour-coded
boxes, an editable form on the right, permanently linked in both directions.
Before the reviewer looks, a battery of checks has already run:

- **Arithmetic** — net + VAT = total.
- **Numbers** — locale-aware parsing (`1.234,56` vs `1,234.56` vs `1 234,56`).
- **Tax & bank identifiers** — structural VAT and IBAN validation, and a
  payment-reference check digit (via python-stdnum).
- **Fraud signal** — supplier country vs bank country mismatch.

Anything that fails is flagged, and the reviewer lands on the first problem.

**Coding.** An invoice is not one project — it carries a set of allocation
lines, one per printed row, each coded to a Marathon project. The rows must sum
exactly to the net total, and a mismatch is flagged.

**Handover.** On approval the coded invoice is delivered to Marathon using the
transactional-outbox pattern: the handover is enqueued in the same database
transaction as the verification, then a separate worker delivers it with
retries. An idempotency key (the invoice fingerprint) guarantees the same
supplier invoice can never be posted twice. Marathon's returned reference is
stored against the invoice and recorded in the audit trail.

## Architecture

```
Browser (React / Vite)
   │  /api
   ▼
FastAPI + Uvicorn ──▶ intake worker (watched folder)
   │                └▶ outbox worker (delivery to Marathon)
   ├─ pypdfium2 ─▶ page images
   ├─ vision model (Claude Opus 4.8)  [or mock]
   ├─ python-stdnum (VAT / IBAN / Luhn)
   ├─ SQLite  (invoices, fields, line_items, audit, outbox)
   └─ filesystem (original PDFs + page images)
                          │
                          ▼
                    Marathon adapter (API / import / Peppol)
```

- **Backend:** Python, FastAPI, Uvicorn.
- **Reading:** pypdfium2, Pillow, Claude Opus 4.8 vision (mock fallback).
- **Validation:** python-stdnum.
- **Store:** SQLite (WAL, STRICT tables) for structured data + audit; filesystem
  for the immutable originals and page images.
- **Frontend:** React, Vite, an SVG overlay bound to the page.

## Data model (SQLite)

| Table | Holds |
|---|---|
| invoices | one row per invoice: filename, status, summary (supplier/total/currency), search text, verification and handover state |
| fields | the extracted header fields (value, confidence, status, box) |
| line_items | the allocation lines (row + amount + assigned project) |
| audit | append-only, hash-chained history of every change |
| outbox | the Marathon handover queue (idempotent, with retries) |

Originals (`original.pdf`) and rendered page images live on disk, not in the DB.

## Key design decisions

- **SQLite as the working store.** With ~1,000 invoices/day and two reviewers,
  and Marathon holding the permanent record, SQLite is the simplest thing that
  fully does the job — no server to run, back up or secure. The design keeps a
  clear path to PostgreSQL if scale ever demands it.
- **Audit trail is append-only and hash-chained.** Every event (ingest, each
  field correction with old→new, project coding, verification, handover) is
  recorded with who and when. Each row's hash includes the previous row's, so
  any later edit or deletion is detectable; an integrity endpoint proves it.
- **Idempotent handover.** The outbox + idempotency key mean a verified invoice
  cannot be lost in transit and cannot be delivered twice.
- **Mock mode.** The system runs end-to-end with no API key or credit, using
  realistic sample invoices — so the verification screen and full workflow can
  be exercised before any billing is set up.

## Current status and what is not yet built

Implemented and working end-to-end (in mock mode): all six pipeline stages, the
SQLite store, the audit trail, and the searchable/paged queue.

Not yet built (from the proposal):

- **Live extraction** is wired but blocked on Developer Platform API billing;
  the code switches from mock to live automatically once a credential with
  credit is present.
- **Online VIES** lookup (confirm a VAT number is *registered*, not just valid),
  reverse-charge recognition, and currency conversion.
- **Layout-fingerprint cache** so previously-seen suppliers are read
  deterministically and cheaply.
- **Object storage** (S3/MinIO), a **PDF.js** overlay, user accounts and
  optional four-eyes approval, and the scheduled **purge** of invoice content
  after confirmed handover.
