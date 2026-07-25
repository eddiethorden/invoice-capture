"""Momskoder och momsberäkning enligt svensk standard.

Handles Swedish input VAT (ingående moms): the standard rates 25/12/6 %, the
zero/exempt case, and *omvänd skattskyldighet* (reverse charge) for construction
(byggmoms) and cross-border services, where the buyer self-assesses both the
output and the (deductible) input VAT.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

ORE = Decimal("0.01")


@dataclass(frozen=True)
class Momskod:
    kod: str
    beskrivning: str
    sats: Decimal              # 0.25, 0.12, 0.06, 0
    omvand: bool = False       # omvänd skattskyldighet (reverse charge)


# Momskoder som stöds i denna milstolpe.
MOMSKODER: dict[str, Momskod] = {
    "SE25": Momskod("SE25", "Ingående moms 25 %", Decimal("0.25")),
    "SE12": Momskod("SE12", "Ingående moms 12 %", Decimal("0.12")),
    "SE06": Momskod("SE06", "Ingående moms 6 %", Decimal("0.06")),
    "SE00": Momskod("SE00", "Momsfritt / ingen moms", Decimal("0")),
    "RC25": Momskod("RC25", "Omvänd skattskyldighet 25 % (bygg / EU-tjänst)",
                    Decimal("0.25"), omvand=True),
}

DEFAULT_MOMSKOD = "SE25"


def momskod(kod: str) -> Momskod:
    try:
        return MOMSKODER[kod]
    except KeyError:
        raise KeyError(f"okänd momskod {kod!r}")


def moms_belopp(netto: Decimal, kod: Momskod) -> Decimal:
    """Momsbelopp på ett nettobelopp, avrundat till öre (kommersiell avrundning).

    Reverse charge räknas på samma nettobelopp — där blir det både en beräknad
    utgående och en avdragsgill ingående moms av samma storlek.
    """
    return (netto * kod.sats).quantize(ORE, rounding=ROUND_HALF_UP)
