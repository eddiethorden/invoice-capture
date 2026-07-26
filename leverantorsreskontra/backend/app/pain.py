"""ISO 20022 pain.001 — betalfil (kreditöverföringar) till banken.

Builds a pain.001.001.03 Customer Credit Transfer Initiation from the coded
supplier invoices: one credit transfer per invoice, paying the leverantörsskuld
to the supplier's IBAN, with the OCR/payment reference as structured remittance.

Payments are grouped into PmtInf blocks by (requested execution date = förfallo-
dag, currency), as the standard expects. Amounts have two decimals; NbOfTxs and
CtrlSum are filled in at both group and message level.

Scope: IBAN-based transfers. Domestic bankgiro/plusgiro (proprietary creditor
id) is a later addition.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from xml.etree import ElementTree as ET

NS = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"
ET.register_namespace("", NS)


def _iso_datum(raw: str | None, fallback: str) -> str:
    if raw:
        raw = raw.strip()
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%Y%m%d"):
            try:
                return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
    return fallback


def _belopp(x) -> Decimal:
    return Decimal(str(x or "0"))


def _sub(parent, tag, text=None):
    e = ET.SubElement(parent, f"{{{NS}}}{tag}")
    if text is not None:
        e.text = str(text)
    return e


def _kort(s: str, n: int = 35) -> str:
    """ID-fält i pain.001 är max 35 tecken."""
    return (s or "")[:n]


class PainError(Exception):
    pass


def _mottagarkonto(tx, b: dict) -> None:
    """Mottagarens konto: bankgiro (BGNR) och plusgiro (PGNR) anges som Othr med
    ett proprietärt schema (svensk inhemsk betalning via Bankgirot), IBAN annars.
    Prioritet: bankgiro > plusgiro > IBAN.

    (Vissa banker vill även ha CdtrAgt med Bankgirots BIC för BG/PG; det utelämnas
    här — schemat BGNR/PGNR pekar ut Bankgirot-routningen — och läggs lätt till.)
    """
    idn = _sub(_sub(tx, "CdtrAcct"), "Id")
    if b.get("bankgiro"):
        othr = _sub(idn, "Othr")
        _sub(othr, "Id", b["bankgiro"])
        _sub(_sub(othr, "SchmeNm"), "Prtry", "BGNR")
    elif b.get("plusgiro"):
        othr = _sub(idn, "Othr")
        _sub(othr, "Id", b["plusgiro"])
        _sub(_sub(othr, "SchmeNm"), "Prtry", "PGNR")
    else:
        _sub(idn, "IBAN", b["iban"])


def bygg_pain001(betalningar: list[dict], *, msg_id: str, cre_dttm: str,
                 initg_nm: str, dbtr_nm: str, dbtr_iban: str, dbtr_bic: str,
                 exctn_fallback: str) -> tuple[str, list[dict]]:
    """Bygg pain.001-XML. Returnerar (xml, hoppade_over).

    Betalningar utan IBAN eller utan positivt belopp hoppas över och returneras
    separat (så anroparen kan rapportera dem).
    """
    betalbara, hoppade = [], []
    for b in betalningar:
        har_konto = b.get("bankgiro") or b.get("plusgiro") or b.get("iban")
        if har_konto and _belopp(b.get("belopp")) > 0:
            betalbara.append(b)
        else:
            hoppade.append(b)
    if not betalbara:
        raise PainError(
            "inga betalbara poster (kräver bankgiro/plusgiro/IBAN och positivt belopp)")

    # Gruppera på (förfallodag, valuta).
    grupper: dict[tuple[str, str], list[dict]] = {}
    for b in betalbara:
        exctn = _iso_datum(b.get("due_date"), exctn_fallback)
        ccy = (b.get("currency") or "SEK").upper()
        grupper.setdefault((exctn, ccy), []).append(b)

    total_antal = len(betalbara)
    total_summa = sum((_belopp(b["belopp"]) for b in betalbara), Decimal("0"))

    root = ET.Element(f"{{{NS}}}Document")
    ccti = _sub(root, "CstmrCdtTrfInitn")

    grp = _sub(ccti, "GrpHdr")
    _sub(grp, "MsgId", _kort(msg_id))
    _sub(grp, "CreDtTm", cre_dttm)
    _sub(grp, "NbOfTxs", total_antal)
    _sub(grp, "CtrlSum", f"{total_summa:.2f}")
    _sub(_sub(grp, "InitgPty"), "Nm", initg_nm)

    for pi, ((exctn, ccy), poster) in enumerate(sorted(grupper.items()), start=1):
        antal = len(poster)
        summa = sum((_belopp(b["belopp"]) for b in poster), Decimal("0"))

        pmt = _sub(ccti, "PmtInf")
        _sub(pmt, "PmtInfId", _kort(f"{msg_id}-{pi}"))
        _sub(pmt, "PmtMtd", "TRF")
        _sub(pmt, "BtchBookg", "true")
        _sub(pmt, "NbOfTxs", antal)
        _sub(pmt, "CtrlSum", f"{summa:.2f}")
        if ccy == "EUR":
            _sub(_sub(_sub(pmt, "PmtTpInf"), "SvcLvl"), "Cd", "SEPA")
        _sub(pmt, "ReqdExctnDt", exctn)
        _sub(_sub(pmt, "Dbtr"), "Nm", dbtr_nm)
        _sub(_sub(_sub(pmt, "DbtrAcct"), "Id"), "IBAN", dbtr_iban)
        if dbtr_bic:
            _sub(_sub(_sub(pmt, "DbtrAgt"), "FinInstnId"), "BIC", dbtr_bic)
        _sub(pmt, "ChrgBr", "SLEV")

        for b in poster:
            tx = _sub(pmt, "CdtTrfTxInf")
            pmtid = _sub(tx, "PmtId")
            _sub(pmtid, "InstrId", _kort(f"{msg_id}-{b['id']}"))
            _sub(pmtid, "EndToEndId", _kort(b.get("invoice_number") or b["id"]))
            amt = _sub(tx, "Amt")
            instd = _sub(amt, "InstdAmt", f"{_belopp(b['belopp']):.2f}")
            instd.set("Ccy", ccy)
            _sub(_sub(tx, "Cdtr"), "Nm", b.get("supplier") or "Leverantör")
            _mottagarkonto(tx, b)
            rmt = _sub(tx, "RmtInf")
            ref = (b.get("payment_reference") or "").strip()
            if ref:
                cdtrref = _sub(_sub(rmt, "Strd"), "CdtrRefInf")
                _sub(_sub(_sub(cdtrref, "Tp"), "CdOrPrtry"), "Prtry", "OCR")
                _sub(cdtrref, "Ref", ref)
            else:
                _sub(rmt, "Ustrd", _kort(f"Faktura {b.get('invoice_number') or b['id']}", 140))

    ET.indent(root, space="  ")
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + \
        ET.tostring(root, encoding="unicode")
    return xml, hoppade


def ny_msg_id(nu: datetime) -> str:
    return "LR" + nu.strftime("%Y%m%d%H%M%S")
