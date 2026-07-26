"""Tester för pain.001-betalfilen.

    backend/.venv/bin/python test_pain.py

Validerar: giltig XML i rätt namnrymd, NbOfTxs/CtrlSum stämmer, gruppering per
förfallodag+valuta, OCR som strukturerad referens, och att poster utan IBAN
hoppas över.
"""

from decimal import Decimal
from xml.etree import ElementTree as ET

from app import pain

NS = pain.NS


def _q(tag):
    return f"{{{NS}}}{tag}"


BETALNINGAR = [
    {"id": "inv-1", "supplier": "Åkerbergs Kontor AB", "invoice_number": "2026-4035",
     "due_date": "2026-08-09", "currency": "SEK", "iban": "SE35 5000 0000 0549 1000 0003",
     "payment_reference": "5566778899", "belopp": "1000.00"},
    {"id": "inv-2", "supplier": "Bygg & Fräs AB", "invoice_number": "2026-4041",
     "due_date": "2026-08-09", "currency": "SEK", "iban": "SE4550000000058398257466",
     "payment_reference": "", "belopp": "500.00"},
    {"id": "inv-3", "supplier": "EU Supplier GmbH", "invoice_number": "R-77",
     "due_date": "2026-09-01", "currency": "EUR", "iban": "DE89370400440532013000",
     "payment_reference": "", "belopp": "250.00"},
    {"id": "inv-4", "supplier": "Utan IBAN AB", "invoice_number": "X-1",
     "due_date": "2026-08-09", "currency": "SEK", "iban": "",
     "payment_reference": "", "belopp": "900.00"},
]

KW = dict(msg_id="LR20260726120000", cre_dttm="2026-07-26T12:00:00",
          initg_nm="KASE AB", dbtr_nm="KASE Technologies AB",
          dbtr_iban="SE1212341234123412341234", dbtr_bic="NDEASESS",
          exctn_fallback="2026-07-26")


def _build():
    xml, hoppade = pain.bygg_pain001(BETALNINGAR, **KW)
    return ET.fromstring(xml), hoppade


def test_giltig_xml_och_summor():
    root, hoppade = _build()
    assert root.tag == _q("Document")
    grp = root.find(f"./{_q('CstmrCdtTrfInitn')}/{_q('GrpHdr')}")
    # tre betalbara (inv-4 saknar IBAN)
    assert grp.find(_q("NbOfTxs")).text == "3"
    assert grp.find(_q("CtrlSum")).text == "1750.00"  # 1000 + 500 + 250
    print("OK  giltig XML, NbOfTxs=3, CtrlSum=1750.00")


def test_gruppering_och_hoppade():
    root, hoppade = _build()
    pmts = root.findall(f"./{_q('CstmrCdtTrfInitn')}/{_q('PmtInf')}")
    # grupper: (2026-08-09, SEK) och (2026-09-01, EUR)
    assert len(pmts) == 2
    exctn = {p.find(_q("ReqdExctnDt")).text for p in pmts}
    assert exctn == {"2026-08-09", "2026-09-01"}
    assert len(hoppade) == 1 and hoppade[0]["id"] == "inv-4"
    print("OK  två PmtInf-grupper (förfallodag+valuta), 1 hoppad utan IBAN")


def test_belopp_referens_och_valuta():
    root, _ = _build()
    txs = root.findall(f".//{_q('CdtTrfTxInf')}")
    assert len(txs) == 3
    # SEK-summa i gruppen
    sek = [t for t in txs if t.find(f"{_q('Amt')}/{_q('InstdAmt')}").get("Ccy") == "SEK"]
    assert len(sek) == 2
    total = sum(Decimal(t.find(f"{_q('Amt')}/{_q('InstdAmt')}").text) for t in txs)
    assert total == Decimal("1750.00")
    # OCR som strukturerad referens på inv-1
    refs = root.findall(f".//{_q('RmtInf')}/{_q('Strd')}/{_q('CdtrRefInf')}/{_q('Ref')}")
    assert any(r.text == "5566778899" for r in refs)
    # EUR-gruppen har SEPA-servicenivå
    eur_pmt = [p for p in root.findall(f".//{_q('PmtInf')}")
               if p.find(f".//{_q('InstdAmt')}").get("Ccy") == "EUR"][0]
    assert eur_pmt.find(f"{_q('PmtTpInf')}/{_q('SvcLvl')}/{_q('Cd')}").text == "SEPA"
    print("OK  belopp, OCR-referens (SCOR/Prtry), SEPA för EUR")


def test_inga_betalbara():
    try:
        pain.bygg_pain001([{"id": "x", "iban": "", "belopp": "0"}], **KW)
    except pain.PainError:
        print("OK  fel när inget är betalbart")
        return
    raise AssertionError("borde ha kastat PainError")


if __name__ == "__main__":
    test_giltig_xml_och_summor()
    test_gruppering_och_hoppade()
    test_belopp_referens_och_valuta()
    test_inga_betalbara()
    print("\nalla pain-tester godkända")
