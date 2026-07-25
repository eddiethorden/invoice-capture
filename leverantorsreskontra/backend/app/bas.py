"""BAS-kontoplan — ett urval relevant för en leverantörsreskontra.

A curated subset of the Swedish BAS chart of accounts (BAS 2025). It holds the
*system accounts* the verifikat-motorn books against (leverantörsskuld, moms)
plus a set of common *kostnadskonton* for coding invoice lines.

OBS: kontonumren följer standard-BAS men ska stämmas av mot KASE:s faktiska
kontoplan — de är avsiktligt samlade här så de är lätta att byta ut.
"""

from __future__ import annotations

from dataclasses import dataclass

# Kontotyper (styr hur kontot får användas i konteringen).
KOSTNAD = "kostnad"
LEVERANTORSSKULD = "leverantorsskuld"
MOMS_INGAENDE = "moms_ingaende"
MOMS_UTGAENDE = "moms_utgaende"
BANK = "bank"


@dataclass(frozen=True)
class Konto:
    nummer: str
    namn: str
    typ: str


# ---- Systemkonton som konteringsmotorn bokar mot ----
# (overridable in future via config; constants for now.)
LEVERANTORSSKULDER = "2440"          # kredit: skuld till leverantör
INGAENDE_MOMS = "2640"               # debet: avdragsgill ingående moms (inhemsk)
BERAKNAD_INGAENDE_MOMS_UTLAND = "2645"  # debet: beräknad ingående moms, förvärv
UTGAENDE_MOMS_OMVANT_25 = "2614"     # kredit: utgående moms omvänd skattskyldighet
FORETAGSKONTO = "1930"               # bank (används vid betalning, ej kontering)

_SYSTEMKONTON = [
    Konto("1930", "Företagskonto / affärskonto", BANK),
    Konto("2440", "Leverantörsskulder", LEVERANTORSSKULD),
    Konto("2614", "Utgående moms omvänd skattskyldighet, 25 %", MOMS_UTGAENDE),
    Konto("2640", "Ingående moms", MOMS_INGAENDE),
    Konto("2645", "Beräknad ingående moms på förvärv från utlandet", MOMS_INGAENDE),
]

# ---- Vanliga kostnadskonton för radkontering ----
_KOSTNADSKONTON = [
    Konto("4010", "Inköp av varor och material", KOSTNAD),
    Konto("4415", "Inköpta tjänster i Sverige, omvänd skattskyldighet", KOSTNAD),
    Konto("4535", "Inköp av tjänster från annat EU-land", KOSTNAD),
    Konto("4531", "Import av tjänster, land utanför EU", KOSTNAD),
    Konto("5010", "Lokalhyra", KOSTNAD),
    Konto("5020", "El för belysning", KOSTNAD),
    Konto("5220", "Hyra av inventarier och verktyg", KOSTNAD),
    Konto("5410", "Förbrukningsinventarier", KOSTNAD),
    Konto("5460", "Förbrukningsmaterial", KOSTNAD),
    Konto("5611", "Drivmedel för personbilar", KOSTNAD),
    Konto("5910", "Annonsering", KOSTNAD),
    Konto("6071", "Representation, avdragsgill", KOSTNAD),
    Konto("6110", "Kontorsmateriel", KOSTNAD),
    Konto("6212", "Mobiltelefon", KOSTNAD),
    Konto("6230", "Datakommunikation", KOSTNAD),
    Konto("6420", "Ersättningar till revisor", KOSTNAD),
    Konto("6530", "Redovisningstjänster", KOSTNAD),
    Konto("6540", "IT-tjänster", KOSTNAD),
    Konto("6570", "Bankkostnader", KOSTNAD),
    Konto("5420", "Programvaror", KOSTNAD),
]

KONTOPLAN: dict[str, Konto] = {k.nummer: k for k in _SYSTEMKONTON + _KOSTNADSKONTON}


def konto(nummer: str) -> Konto:
    try:
        return KONTOPLAN[nummer]
    except KeyError:
        raise KeyError(f"okänt konto {nummer!r} — finns inte i kontoplanen")


def kostnadskonton() -> list[Konto]:
    """Konton valbara för radkontering (för UI-dropdown)."""
    return list(_KOSTNADSKONTON)
