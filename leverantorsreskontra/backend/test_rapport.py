"""Tester för rapportbyggaren (godkända fakturor).

    backend/.venv/bin/python test_rapport.py
"""

from datetime import datetime

from app import rapport

ROWS = [
    {"supplier": "Åkerbergs Kontor AB", "invoice_number": "2026-4005",
     "invoice_date": "09.08.2026", "due_date": "08.09.2026",
     "total": "1.103,35", "currency": "EUR", "attest_status": "granskad"},
    {"supplier": "Bygg & Fräs AB", "invoice_number": "2026-4007",
     "invoice_date": "2026-07-31", "due_date": "2026-08-30",
     "total": "1.987,82", "currency": "EUR", "attest_status": "attesterad"},
]


def test_html():
    h = rapport.bygg_html(ROWS, datetime(2026, 7, 28, 10, 0, 0))
    assert "Åkerbergs Kontor AB" in h and "Bygg &amp; Fräs AB" in h   # escaping
    assert "2026-08-09" in h                       # dd.mm.yyyy -> ISO
    assert "3 091,17 EUR" in h                      # summa 1103.35 + 1987.82
    assert "1 granskade · 1 attesterade" in h
    assert ">Attesterad<" in h and ">Granskad<" in h
    print("OK  HTML: rader, escaping, ISO-datum, summa, statusräkning")


def test_csv():
    c = rapport.bygg_csv(ROWS)
    assert c.startswith("﻿")               # BOM för Excel
    lines = c.lstrip("﻿").strip().split("\r\n")
    assert lines[0].startswith("Leverantör;Fakturanr")
    assert len(lines) == 3                          # rubrik + 2 rader
    assert "2026-4005;2026-08-09;2026-09-08;1.103,35;EUR;Granskad" in lines[1]
    print("OK  CSV: BOM, semikolon, rubrik + rader")


def test_tom():
    h = rapport.bygg_html([], datetime(2026, 7, 28))
    assert "Inga godkända fakturor" in h and 'id="antal">0</div>' in h
    print("OK  tom lista: 0 fakturor, tomrad")


def test_json():
    d = rapport.rapport_data(ROWS, datetime(2026, 7, 28, 9, 30, 0))
    assert d["antal"] == 2 and d["summa"] == "3 091,17 EUR"
    assert d["statusrad"] == "1 granskade · 1 attesterade"
    assert d["rader"][1]["cls"] == "ok" and d["rader"][1]["invoice_date"] == "2026-07-31"
    print("OK  JSON-data: antal, summa, status, rad-cls/datum")


if __name__ == "__main__":
    test_html()
    test_csv()
    test_tom()
    test_json()
    print("\nalla rapport-tester godkända")
