"""Stage 4 prep - arithmetic and structural checks that run before a human
ever sees the invoice, so the reviewer's attention goes straight to problems.

Multi-country number parsing is the single largest source of silent error, so
number parsing is deliberate: we infer the decimal separator from the string
rather than assuming a locale.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from .fields import AMOUNT_FIELDS, FIELD_DEFS
from .models import Field_, LineItem, NormBox, RawExtraction, RawField
from .validators import (validate_bankgiro, validate_iban, validate_payment_reference,
                         validate_plusgiro, validate_vat)

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


def _norm_box(x0, y0, x1, y1, page, page_dims) -> NormBox | None:
    if not (x1 > x0 and y1 > y0):
        return None
    pw, ph = page_dims[page] if page < len(page_dims) else page_dims[0]
    return NormBox(
        x0=max(0.0, x0 / pw), y0=max(0.0, y0 / ph),
        x1=min(1.0, x1 / pw), y1=min(1.0, y1 / ph),
    )


def build_line_items(
    raw: RawExtraction, page_dims: list[tuple[int, int]], net: Decimal | None
) -> tuple[list[LineItem], dict | None]:
    """Build allocation lines from the invoice rows and check they sum to net."""
    items: list[LineItem] = []
    row_total = Decimal("0")
    all_parsed = True
    for i, r in enumerate(raw.line_items):
        amt = parse_amount(r.amount)
        if amt is None:
            all_parsed = False
        else:
            row_total += amt
        status = "amber" if (r.confidence < LOW_CONFIDENCE or amt is None) else "green"
        items.append(
            LineItem(
                index=i,
                description=r.description,
                quantity=r.quantity,
                unit_price=r.unit_price,
                amount=r.amount,
                confidence=round(r.confidence, 2),
                page=r.page,
                status=status,
                box=_norm_box(r.x0, r.y0, r.x1, r.y1, r.page, page_dims),
                project="",
            )
        )

    rows_check: dict | None = None
    if items and net is not None and all_parsed:
        ok = abs(row_total - net) <= Decimal("0.02")
        rows_check = {
            "ok": ok,
            "row_total": str(row_total),
            "net": str(net),
        }
        if not ok:
            # The rows disagree with the stated net - flag every row.
            for it in items:
                if it.status != "amber":
                    it.status = "amber"
    return items, rows_check


def build_fields(
    raw: RawExtraction, page_dims: list[tuple[int, int]]
) -> tuple[list[Field_], list[LineItem], dict, list[dict]]:
    """Normalize boxes, run checks, assign a display status per field, capture
    the allocation lines, and return structural-validation signals."""
    net = parse_amount(getattr(raw, "net_amount").value)
    vat = parse_amount(getattr(raw, "vat_amount").value)
    total = parse_amount(getattr(raw, "total_amount").value)

    arithmetic_ok: bool | None = None
    message = "Netto + moms kunde inte kontrolleras (ett belopp saknas eller är oläsligt)."
    if net is not None and vat is not None and total is not None:
        arithmetic_ok = abs((net + vat) - total) <= Decimal("0.02")
        message = (
            "Netto + moms = totalt stämmer."
            if arithmetic_ok
            else f"Netto + moms ({net + vat}) är inte lika med totalt ({total})."
        )

    # Per-country structural validation on the identifiers.
    vat_res = validate_vat(getattr(raw, "vat_number").value)
    iban_res = validate_iban(getattr(raw, "iban").value)
    ref_res = validate_payment_reference(getattr(raw, "payment_reference").value)
    bg_res = validate_bankgiro(getattr(raw, "bankgiro").value)
    pg_res = validate_plusgiro(getattr(raw, "plusgiro").value)

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
            elif key == "bankgiro" and bg_res and bg_res["valid"] is False:
                status = "red"
            elif key == "plusgiro" and pg_res and pg_res["valid"] is False:
                status = "red"

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

    line_items, rows_check = build_line_items(raw, page_dims, net)

    checks = {"arithmetic_ok": arithmetic_ok, "message": message}
    signals = _signals(vat_res, iban_res, ref_res, country_mismatch,
                       supplier_country, bank_country)
    for res, name in ((bg_res, "bankgiro"), (pg_res, "plusgiro")):
        if res and res["valid"] is True:
            signals.append({"level": "ok", "field": name,
                            "message": f"{name.capitalize()} har giltig kontrollsiffra."})
        elif res and res["valid"] is False:
            signals.append({"level": "error", "field": name,
                            "message": f"{name.capitalize()} har ogiltig kontrollsiffra."})
    if rows_check is not None:
        if rows_check["ok"]:
            signals.append({"level": "ok", "field": None,
                            "message": f"Raderna summerar till nettobeloppet ({rows_check['net']})."})
        else:
            signals.append({"level": "error", "field": None,
                            "message": (f"Raderna summerar till {rows_check['row_total']}, "
                                        f"vilket inte stämmer med nettobeloppet ({rows_check['net']}).")})
    elif line_items:
        signals.append({"level": "warn", "field": None,
                        "message": "Raderna kunde inte stämmas av mot nettobeloppet."})
    return fields, line_items, checks, signals


def _signals(vat_res, iban_res, ref_res, mismatch, supplier_country, bank_country) -> list[dict]:
    out: list[dict] = []
    if vat_res:
        if vat_res["valid"] is True:
            out.append({"level": "ok", "field": "vat_number",
                        "message": f"Momsreg.nr är strukturellt giltigt ({vat_res['country']})."})
        elif vat_res["valid"] is False:
            out.append({"level": "error", "field": "vat_number",
                        "message": "Momsreg.nr klarar inte den nationella strukturkontrollen."})
    if iban_res:
        if iban_res["valid"] is True:
            out.append({"level": "ok", "field": "iban",
                        "message": f"IBAN-kontrollsumman är giltig ({iban_res['country']})."})
        elif iban_res["valid"] is False:
            out.append({"level": "error", "field": "iban",
                        "message": "IBAN-kontrollsumman är ogiltig."})
    if mismatch:
        out.append({"level": "warn", "field": "iban",
                    "message": (f"Leverantörens land ({supplier_country}) skiljer sig från bankens "
                                f"land ({bank_country}) – en vanlig indikation på fakturabedrägeri.")})
    if ref_res is not None:
        if ref_res["valid"] is True:
            out.append({"level": "ok", "field": "payment_reference",
                        "message": "Betalreferensen har giltig kontrollsiffra."})
        elif ref_res["valid"] is False:
            out.append({"level": "warn", "field": "payment_reference",
                        "message": "Betalreferensen har ogiltig kontrollsiffra."})
    return out


def _status(key: str, rf: RawField, arithmetic_ok: bool | None) -> str:
    if not rf.found:
        return "grey"
    if key in AMOUNT_FIELDS and arithmetic_ok is False:
        return "red"
    if rf.confidence < LOW_CONFIDENCE:
        return "amber"
    return "green"
