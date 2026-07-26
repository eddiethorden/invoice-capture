#!/usr/bin/env bash
# Browser test environment for the Leverantörsreskontra app.
#
#   ./dev.sh                 start backend (:8000), AR module (:8020) + frontend
#                            (:5173); Ctrl+C stops all three
#   ./dev.sh --seed 12       (re)generate 12 sample invoices first, then start
#
# AR module data persists in backend/data/ar.db across restarts; it starts empty
# on a fresh checkout (post a receivable to its intake API to populate).
#
# Prereqs (one-time):
#   cd backend && python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
#   cd frontend && npm install
#
# Runs in MOCK extraction mode (no ANTHROPIC_API_KEY) — each sample invoice
# opens with its own recorded ground truth. Open http://localhost:5173.
set -e
cd "$(dirname "$0")"

# Test config (override by exporting before running).
export ATTEST_BELOPPSGRANS=${ATTEST_BELOPPSGRANS:-100000}
export SIE_FNAMN=${SIE_FNAMN:-"KASE Technologies AB"}
export SIE_ORGNR=${SIE_ORGNR:-"556677-8899"}
export SIE_SIGN=${SIE_SIGN:-"ET"}
export PAIN_DBTR_NM=${PAIN_DBTR_NM:-"KASE Technologies AB"}
export PAIN_DBTR_IBAN=${PAIN_DBTR_IBAN:-"SE1212341234123412341234"}
export PAIN_DBTR_BIC=${PAIN_DBTR_BIC:-"NDEASESS"}
# Force mock extraction — the OAuth profile counts as a credential, so unsetting
# ANTHROPIC_API_KEY isn't enough to avoid live API calls.
export INVOICE_CAPTURE_MOCK=${INVOICE_CAPTURE_MOCK:-1}
unset ANTHROPIC_API_KEY

if [ "$1" = "--seed" ]; then
  ( cd backend && ./.venv/bin/python make_samples.py "${2:-12}" )
fi

( cd backend && exec ./.venv/bin/python -m uvicorn app.main:app --port 8000 ) &
BACK=$!
( cd backend && exec ./.venv/bin/python -m uvicorn ar_module:app --port 8020 ) &
AR=$!
trap "kill $BACK $AR 2>/dev/null" EXIT

( cd frontend && exec npm run dev )
