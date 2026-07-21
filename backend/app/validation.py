"""Stage 4 prep - arithmetic and structural checks that run before a human
ever sees the invoice, so the reviewer's attention goes straight to problems.

Multi-country number parsing is the single largest source of silent error, so
number parsing is deliberate: we infer the decimal separator from the string
rather than assuming a locale.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from .fields import AMOUNT_FIELDS, FIELD_DEFS
from .models import Field_, NormBox, RawExtraction, RawField
from .validators import validate_iban, validate_payment_reference, validate_vat

LOW_CONFIDENCE = 0.60


def parse_amount(raw: str) -> Decimal | None:
    """Parse a monetary string without assuming a locale.

    Handles '1.234,56' (European), '1,234.56' (US/UK), '1 234,56' (French),
    "1'234.56" (Swiss). The rightmost of the last '.' or ',' is treated as the
    decimal separator; everything else is grouping and stripped.
    """
    if not raw:
        return None
    s = raw.strip()
    # keep digits, separators and a leading sign
    cleaned = "".join(ch for ch in s if ch.isdigit() or ch in ".,'  -")
    cleaned = cleaned.replace(" ", "").replace(" ", "").replace("'", "")
    if not any(ch.isdigit() for ch in cleaned):
        return None

    last_dot = cleaned.rfind(".")
    last_comma = cleaned.rfind(",")
    dec_pos = max(last_dot, last_comma)

    if dec_pos == -1:
        number = cleaned
    else:
        tail = cleaned[dec_pos + 1 :]
        only_one_sep = (last_dot == -1) != (last_comma == -1)
        # A single separator followed by exactly 3 digits is ambiguous
        # ("1,234"); treat it as grouping, not a decimal point.
        if only_one_sep and len(tail) == 3:
            number = cleaned.replace(".", "").replace(",", "")
        else:
            int_part = cleaned[:dec_pos].replace(".", "").replace(",", "")
            number = f"{int_part}.{tail}" if tail else int_part

    try:
        return Decimal(number)
    except InvalidOperation:
        return None


def build_fields(
    raw: RawExtraction, page_dims: list[tuple[int, int]]
) -> tuple[list[Field_], dict, list[dict]]:
    """Normalize boxes, run checks, assign a display status per field, and
    return structural-validation signals for the reviewer."""
    net = parse_amount(getattr(raw, "net_amount").value)
    vat = parse_amount(getattr(raw, "vat_amount").value)
    total = parse_amount(getattr(raw, "total_amount").value)

    arithmetic_ok: bool | None = None
    message = "Net + VAT could not be checked (a figure is missing or unreadable)."
    if net is not None and vat is not None and total is not None:
        arithmetic_ok = abs((net + vat) - total) <= Decimal("0.02")
        message = (
            "Net + VAT = Total checks out."
            if arithmetic_ok
            else f"Net + VAT ({net + vat}) does not equal Total ({total})."
        )

    # Per-country structural validation on the identifiers.
    vat_res = validate_vat(getattr(raw, "vat_number").value)
    iban_res = validate_iban(getattr(raw, "iban").value)
    ref_res = validate_payment_reference(getattr(raw, "payment_reference").value)

    supplier_country = vat_res["country"] if vat_res else None
    bank_country = iban_res["country"] if iban_res else None
    country_mismatch = bool(
        supplier_country and bank_country and supplier_country != bank_country
    )

    fields: list[Field_] = []
    for key, label, _sv in FIELD_DEFS:
        rf: RawField = getattr(raw, key)
        status = _status(key, rf, arithmetic_ok)

        # Structural checks escalate status beyond confidence alone.
        if rf.found:
            if key == "vat_number" and vat_res and vat_res["valid"] is False:
                status = "red"
            elif key == "iban":
                if iban_res and iban_res["valid"] is False:
                    status = "red"
                elif country_mismatch and status != "red":
                    status = "amber"
            elif key == "payment_reference" and ref_res and ref_res["valid"] is False:
                status = "amber" if status != "red" else status

        box = None
        if rf.found and (rf.x1 > rf.x0 and rf.y1 > rf.y0):
            pw, ph = page_dims[rf.page] if rf.page < len(page_dims) else page_dims[0]
            box = NormBox(
                x0=max(0.0, rf.x0 / pw),
                y0=max(0.0, rf.y0 / ph),
                x1=min(1.0, rf.x1 / pw),
                y1=min(1.0, rf.y1 / ph),
            )
        fields.append(
            Field_(
                key=key,
                label=label,
                value=rf.value,
                confidence=round(rf.confidence, 2),
                found=rf.found,
                page=rf.page,
                status=status,
                box=box,
            )
        )

    checks = {"arithmetic_ok": arithmetic_ok, "message": message}
    signals = _signals(vat_res, iban_res, ref_res, country_mismatch,
                       supplier_country, bank_country)
    return fields, checks, signals


def _signals(vat_res, iban_res, ref_res, mismatch, supplier_country, bank_country) -> list[dict]:
    out: list[dict] = []
    if vat_res:
        if vat_res["valid"] is True:
            out.append({"level": "ok", "field": "vat_number",
                        "message": f"VAT number is structurally valid ({vat_res['country']})."})
        elif vat_res["valid"] is False:
            out.append({"level": "error", "field": "vat_number",
                        "message": "VAT number fails its national structural check."})
    if iban_res:
        if iban_res["valid"] is True:
            out.append({"level": "ok", "field": "iban",
                        "message": f"IBAN checksum is valid ({iban_res['country']})."})
        elif iban_res["valid"] is False:
            out.append({"level": "error", "field": "iban",
                        "message": "IBAN checksum is invalid."})
    if mismatch:
        out.append({"level": "warn", "field": "iban",
                    "message": (f"Supplier country ({supplier_country}) differs from the bank "
                                f"country ({bank_country}) - a common indicator of invoice fraud.")})
    if ref_res is not None:
        if ref_res["valid"] is True:
            out.append({"level": "ok", "field": "payment_reference",
                        "message": "Payment reference passes its check digit."})
        elif ref_res["valid"] is False:
            out.append({"level": "warn", "field": "payment_reference",
                        "message": "Payment reference does not pass its check digit."})
    return out


def _status(key: str, rf: RawField, arithmetic_ok: bool | None) -> str:
    if not rf.found:
        return "grey"
    if key in AMOUNT_FIELDS and arithmetic_ok is False:
        return "red"
    if rf.confidence < LOW_CONFIDENCE:
        return "amber"
    return "green"
