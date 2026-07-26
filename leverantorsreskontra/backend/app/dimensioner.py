"""Konteringsdimensioner — kostnadsställe.

Kostnadsställe (KS) är **dimension 1** i SIE-standarden. Detta är en liten,
utbytbar uppsättning kostnadsställen; i skarp drift kommer de från KASE:s
register.
"""

from __future__ import annotations

# SIE-dimensionsnummer för kostnadsställe.
SIE_DIM_KOSTNADSSTALLE = 1

_KOSTNADSSTALLEN = {
    "10": "Administration",
    "20": "Försäljning",
    "30": "Produktion",
    "40": "IT",
    "50": "Lager & logistik",
    "60": "Ledning",
}


def kostnadsstallen() -> list[dict]:
    return [{"kod": k, "namn": v} for k, v in _KOSTNADSSTALLEN.items()]


def namn(kod: str) -> str:
    return _KOSTNADSSTALLEN.get(kod, kod)
