"""Konteringsmotor — bygger ett balanserat verifikat från en konterad faktura.

Given supplier-invoice lines each coded to a BAS cost account and a momskod,
produce a balanced double-entry verifikat:

  Inhemsk faktura (t.ex. 25 %):
    Debet  kostnadskonto        netto
    Debet  2640 ingående moms   moms
    Kredit 2440 leverantörsskuld netto + moms

  Omvänd skattskyldighet (buyer self-assesses VAT; supplier bills net only):
    Debet  kostnadskonto              netto
    Debet  2645 beräknad ingående moms moms
    Kredit 2614 utgående moms omvänd   moms
    Kredit 2440 leverantörsskuld       netto

The verifikat is guaranteed to balance (Σ debet == Σ kredit); construction plus
a final assertion enforce it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from . import bas, moms


@dataclass
class Konteringsrad:
    """En konterad fakturarad (indata)."""
    konto: str            # BAS-kostnadskonto
    netto: Decimal        # nettobelopp (exkl. moms)
    momskod: str          # nyckel i moms.MOMSKODER
    beskrivning: str = ""


@dataclass
class Verifikatrad:
    """En rad i det bokförda verifikatet (utdata)."""
    konto: str
    kontonamn: str
    debet: Decimal
    kredit: Decimal
    text: str = ""


@dataclass
class Verifikat:
    rader: list[Verifikatrad] = field(default_factory=list)
    summa_debet: Decimal = Decimal("0")
    summa_kredit: Decimal = Decimal("0")
    balanserar: bool = True
    differens_mot_angivet_total: Decimal | None = None  # om ett bruttototal angetts


def _namn(nummer: str) -> str:
    try:
        return bas.konto(nummer).namn
    except KeyError:
        return nummer


def bygg_verifikat(rader: list[Konteringsrad],
                   angivet_total: Decimal | None = None) -> Verifikat:
    """Bygg ett balanserat verifikat av konterade rader.

    angivet_total: fakturans utskrivna bruttototal, om känt — jämförs mot den
    beräknade leverantörsskulden och differensen (öresavrundning m.m.) returneras.
    """
    if not rader:
        raise ValueError("inga konteringsrader")

    ver = Verifikat()
    ingaende_moms = Decimal("0")   # aggregeras till en 2640-rad
    leverantorsskuld = Decimal("0")

    for r in rader:
        kod = moms.momskod(r.momskod)
        kt = bas.konto(r.konto)
        if kt.typ != bas.KOSTNAD:
            raise ValueError(f"konto {r.konto} ({kt.namn}) är inte ett kostnadskonto")
        netto = r.netto
        skatt = moms.moms_belopp(netto, kod)

        # Debet kostnadskonto (netto)
        ver.rader.append(Verifikatrad(r.konto, kt.namn, netto, Decimal("0"),
                                      r.beskrivning))

        if kod.omvand:
            # Omvänd skattskyldighet: beräknad ingående (debet) + utgående (kredit).
            ver.rader.append(Verifikatrad(
                bas.BERAKNAD_INGAENDE_MOMS_UTLAND,
                _namn(bas.BERAKNAD_INGAENDE_MOMS_UTLAND), skatt, Decimal("0"),
                f"beräknad ingående moms {kod.kod}"))
            ver.rader.append(Verifikatrad(
                bas.UTGAENDE_MOMS_OMVANT_25,
                _namn(bas.UTGAENDE_MOMS_OMVANT_25), Decimal("0"), skatt,
                f"utgående moms omvänd skattskyldighet {kod.kod}"))
            leverantorsskuld += netto
        else:
            ingaende_moms += skatt
            leverantorsskuld += netto + skatt

    # En samlad rad för avdragsgill ingående moms (2640).
    if ingaende_moms > 0:
        ver.rader.append(Verifikatrad(
            bas.INGAENDE_MOMS, _namn(bas.INGAENDE_MOMS),
            ingaende_moms, Decimal("0"), "ingående moms"))

    # Leverantörsskulden (2440) krediteras.
    ver.rader.append(Verifikatrad(
        bas.LEVERANTORSSKULDER, _namn(bas.LEVERANTORSSKULDER),
        Decimal("0"), leverantorsskuld, "leverantörsskuld"))

    ver.summa_debet = sum((v.debet for v in ver.rader), Decimal("0"))
    ver.summa_kredit = sum((v.kredit for v in ver.rader), Decimal("0"))
    ver.balanserar = ver.summa_debet == ver.summa_kredit
    if angivet_total is not None:
        ver.differens_mot_angivet_total = (leverantorsskuld - angivet_total)

    # Ska aldrig inträffa givet konstruktionen — men fånga avrundningsfel tidigt.
    assert ver.balanserar, (
        f"verifikatet balanserar inte: debet {ver.summa_debet} != "
        f"kredit {ver.summa_kredit}")
    return ver
