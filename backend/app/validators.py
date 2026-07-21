"""Per-country structural validation of the identifiers on an invoice.

Multi-country intake is the single largest source of silent error, so these
checks run before a human ever sees the invoice. They are deliberately
structural (checksums and national rules via python-stdnum) - a VIES lookup
that confirms a VAT number is genuinely *registered* is a separate, online
step and is treated as "unverified" rather than "invalid" when unavailable.

Each validator returns a dict with:
  valid   True | False | None   (None = could not be checked)
  country ISO code inferred from the identifier, or None
  value   the normalized identifier
"""

from __future__ import annotations

from stdnum import iban as _iban
from stdnum import luhn
from stdnum.eu import vat as _eu_vat


def validate_vat(raw: str) -> dict | None:
    """Structural validation of an EU VAT registration number."""
    if not raw or not raw.strip():
        return None
    num = raw.replace(" ", "").replace(".", "").replace("-", "").upper()
    country = num[:2] if len(num) >= 2 and num[:2].isalpha() else None
    try:
        valid = _eu_vat.is_valid(num)
    except Exception:
        valid = None
    return {"valid": valid, "country": country, "value": num}


def validate_iban(raw: str) -> dict | None:
    """IBAN checksum validation (covers most of Europe)."""
    if not raw or not raw.strip():
        return None
    num = raw.replace(" ", "").upper()
    country = num[:2] if len(num) >= 2 and num[:2].isalpha() else None
    try:
        valid = _iban.is_valid(num)
    except Exception:
        valid = False
    return {"valid": valid, "country": country, "value": num}


def validate_payment_reference(raw: str) -> dict | None:
    """Check-digit validation of a numeric payment reference (Swedish OCR and
    many structured references use the Luhn/mod-10 scheme)."""
    if not raw or not raw.strip():
        return None
    digits = "".join(c for c in raw if c.isdigit())
    if len(digits) < 2:
        return None
    try:
        valid = luhn.is_valid(digits)
    except Exception:
        valid = None
    return {"valid": valid, "country": None, "value": digits}
