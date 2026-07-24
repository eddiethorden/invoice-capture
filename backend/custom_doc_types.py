"""Fortnox custom-document-type rules, shared by the AP and AR modules.

A custom document's referenceType must match [a-zA-Z0-9_-] (1..25 chars) and may
not be one of Fortnox's reserved built-in types. The reserved check is
normalised — dashes/underscores stripped and upper-cased — so KUND-ORDER,
kund_order and KUNDORDER all collide with the reserved KUNDORDER.
"""

from __future__ import annotations

import re

REFERENCE_TYPE_RE = re.compile(r"^[a-zA-Z0-9_-]{1,25}$")

RESERVED = {
    "ARTICLEPRODUCTION", "ARTIKELPRODUKTION", "CUSTOMERINVOICE", "CUSTOMERORDER",
    "DELIVERYNOTE", "FAKTURA", "FÖLJESEDEL", "INGÅENDESALDO", "INKÖP",
    "INKÖPSORDER", "INVENTERING", "INVENTORY", "INVOICE", "ITEMPRODUCTION",
    "KREDITFAKTURA", "KREDITORDER", "KUNDFAKTURA", "KUNDORDER", "LAGERFLYTT",
    "LEGACYINTEGRATIONIN", "LEGACYINTEGRATIONOUT", "LEVERANTÖRSFAKTURA",
    "LEVFAKTURA", "MANUALDELIVERY", "MANUALINBOUND", "MANUALINBOUNDDELIVERY",
    "MANUALOUTBOUND", "MANUALOUTBOUNDDELIVERY", "MANUELLINLEVERANS",
    "MANUELLLEVERANS", "MANUELLUTLEVERANS", "NEGATIVEOPENINGBALANCES",
    "NEGATIVTINGÅENDESALDO", "ORDER", "PLOCKLISTA", "POSITIVEOPENINGBALANCES",
    "PRODUCTION", "PRODUKTION", "PURCHASE", "PURCHASEORDER", "STOCKTAKING",
    "STOCKTAKINGDEVIATION", "STOCKTRANSFER", "SUPINVOICE", "SUPPLIERINVOICE",
}


def normalise(reference_type: str) -> str:
    return reference_type.replace("-", "").replace("_", "").upper()


_RESERVED_NORMALISED = {normalise(r) for r in RESERVED}


def reference_type_allowed(reference_type: str) -> bool:
    return (bool(REFERENCE_TYPE_RE.match(reference_type))
            and normalise(reference_type) not in _RESERVED_NORMALISED)
