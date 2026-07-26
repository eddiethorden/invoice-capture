"""Konteringsdimensioner — kostnadsställe.

Kostnadsställe (KS) är **dimension 1** i SIE-standarden. Detta är en liten,
utbytbar uppsättning kostnadsställen; i skarp drift kommer de från KASE:s
register.
"""

from __future__ import annotations

# SIE-dimensionsnummer (standard): kostnadsställe = 1, projekt = 6.
SIE_DIM_KOSTNADSSTALLE = 1
SIE_DIM_PROJEKT = 6

_KOSTNADSSTALLEN = {
    "10": "Administration",
    "20": "Försäljning",
    "30": "Produktion",
    "40": "IT",
    "50": "Lager & logistik",
    "60": "Ledning",
}

_PROJEKT = {
    "1001": "Kontorsflytt 2026",
    "1002": "Webbplattform",
    "1003": "ERP-införande",
    "1004": "Marknadskampanj Q3",
}


def kostnadsstallen() -> list[dict]:
    return [{"kod": k, "namn": v} for k, v in _KOSTNADSSTALLEN.items()]


def namn(kod: str) -> str:
    return _KOSTNADSSTALLEN.get(kod, kod)


def projekt() -> list[dict]:
    return [{"kod": k, "namn": v} for k, v in _PROJEKT.items()]


def projekt_namn(kod: str) -> str:
    return _PROJEKT.get(kod, kod)
