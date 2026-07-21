"""Stage 3 - interpretation.

Sends the rendered page images to Claude's vision model and asks for the
invoice fields, each with a confidence score and a bounding box in the pixel
coordinate space of the image it was shown. Opus 4.8's high-resolution vision
returns coordinates that map 1:1 to image pixels, which is what makes the
verification overlay line up with the words beneath it.

If ANTHROPIC_API_KEY is unset, a deterministic mock extraction is returned so
the verification screen can be exercised end-to-end without a key.
"""

from __future__ import annotations

import base64
import io
import logging
import os

from PIL import Image

from .fields import FIELD_KEYS
from .models import RawExtraction, RawField, RawLineItem
from .pdf_utils import RenderedPage

log = logging.getLogger("invoice.extraction")

MODEL = "claude-opus-4-8"

# Cap how many page images we send in one extraction request, to bound cost and
# token usage. The fields that matter almost always sit in the first few pages;
# if a real invoice needs more, raise this or make it per-supplier.
MAX_PAGES = int(os.environ.get("INVOICE_MAX_PAGES", "8"))


def _has_ant_profile() -> bool:
    """True if an `ant auth login` OAuth profile exists on disk.

    The Anthropic SDK resolves these profiles automatically, so a bare
    Anthropic() client authenticates without an env var - but we still need to
    know one exists to choose live over mock.
    """
    from pathlib import Path

    config_dir = os.environ.get("ANTHROPIC_CONFIG_DIR")
    roots = [Path(config_dir)] if config_dir else [
        Path.home() / ".config" / "anthropic",
    ]
    for root in roots:
        creds = root / "credentials"
        if creds.is_dir() and any(creds.glob("*.json")):
            return True
    return False


def _has_credential() -> bool:
    """Real extraction runs when the SDK has any credential to authenticate with.

    Force mock regardless with INVOICE_CAPTURE_MOCK=1;
    force live with INVOICE_CAPTURE_LIVE=1.
    """
    if os.environ.get("INVOICE_CAPTURE_MOCK") == "1":
        return False
    if os.environ.get("INVOICE_CAPTURE_LIVE") == "1":
        return True
    return bool(
        os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("ANTHROPIC_AUTH_TOKEN")
        or _has_ant_profile()
    )

SYSTEM = (
    "You are an expert accounts-payable clerk reading supplier invoices from "
    "any country and in any language. You never guess: if a value is not "
    "clearly present you mark it as not found rather than inventing one."
)

INSTRUCTIONS = """\
You are shown the page images of a single supplier invoice, in order. Each \
image is {sizes}.

Extract these fields:
- supplier_name: the company issuing the invoice (the seller, not the buyer)
- invoice_number: the supplier's invoice number
- invoice_date: the date the invoice was issued, exactly as printed
- due_date: the payment due date, exactly as printed
- currency: the currency code or symbol (e.g. EUR, SEK, USD)
- net_amount: the total excluding VAT, exactly as printed
- vat_amount: the VAT/tax amount, exactly as printed
- total_amount: the grand total including VAT, exactly as printed
- vat_number: the supplier's VAT registration number
- payment_reference: the payment/OCR reference, giro or structured reference
- iban: the supplier's IBAN or bank account number
- po_reference: any purchase-order, order or project number quoted on the invoice

For every field return:
- found: true only if the value is clearly present on a page
- value: the text exactly as it appears (do not reformat numbers or dates)
- confidence: 0.0-1.0, honest about legibility and ambiguity
- page: the 0-based index of the page the value is on
- x0, y0, x1, y1: a tight bounding box around the value, in pixels of that \
page image (x from left, y from top)

If a field is not present, set found=false, value="", confidence=0, page=0, \
and the box to zeros. Return every field, even the missing ones.

Also return line_items: every row of the invoice's line-item table, top to \
bottom. For each row give description, quantity, unit_price and amount exactly \
as printed (use "" where a column is blank), a confidence, the page, and a \
bounding box in pixels around the whole row. Do not include the totals \
(net/VAT/total) as line items - only the itemised rows.
"""


def _encode(image: Image.Image) -> str:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return base64.standard_b64encode(buf.getvalue()).decode("ascii")


def extract(pages: list[RenderedPage]) -> RawExtraction:
    if not _has_credential():
        log.info("No credential found; returning mock extraction.")
        return _mock(pages)

    import anthropic

    client = anthropic.Anthropic()

    sent = pages[:MAX_PAGES]
    if len(pages) > len(sent):
        log.warning(
            "Invoice has %d pages; sending only the first %d for extraction.",
            len(pages),
            len(sent),
        )

    sizes = ", ".join(f"page {i}: {p.width}x{p.height}px" for i, p in enumerate(sent))
    content: list[dict] = [
        {"type": "text", "text": INSTRUCTIONS.format(sizes=sizes)},
    ]
    for p in sent:
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": _encode(p.image),
                },
            }
        )

    response = client.messages.parse(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM,
        messages=[{"role": "user", "content": content}],
        output_format=RawExtraction,
    )
    parsed = response.parsed_output
    if parsed is None:
        # Model refused or returned unparseable output; fall back to empties.
        return _empty()
    return parsed


def _empty() -> RawExtraction:
    blank = {
        k: RawField(found=False, value="", confidence=0.0, page=0, x0=0, y0=0, x1=0, y1=0)
        for k in FIELD_KEYS
    }
    return RawExtraction(line_items=[], **blank)


def _mock(pages: list[RenderedPage]) -> RawExtraction:
    """Deterministic sample so the UI runs without an API key.

    Boxes are placed relative to the first page's dimensions.
    """
    w = pages[0].width if pages else 1000
    h = pages[0].height if pages else 1400

    def box(fx0, fy0, fx1, fy1):
        return dict(x0=int(fx0 * w), y0=int(fy0 * h), x1=int(fx1 * w), y1=int(fy1 * h))

    def f(value, conf, fx0, fy0, fx1, fy1, found=True):
        return RawField(found=found, value=value, confidence=conf, page=0, **box(fx0, fy0, fx1, fy1))

    def row(desc, qty, unit, amt, conf, fy0, fy1):
        return RawLineItem(
            description=desc, quantity=qty, unit_price=unit, amount=amt,
            confidence=conf, page=0, **box(0.07, fy0, 0.93, fy1)
        )

    line_items = [
        row("Freight forwarding, Hamburg - Stockholm", "1", "890,00", "890,00", 0.93, 0.272, 0.292),
        row("Customs handling fee", "1", "120,00", "120,00", 0.9, 0.295, 0.315),
        row("Fuel surcharge", "1", "224,00", "224,00", 0.55, 0.318, 0.338),
    ]

    return RawExtraction(
        line_items=line_items,
        supplier_name=f("Nordwind Logistik GmbH", 0.97, 0.06, 0.05, 0.42, 0.09),
        invoice_number=f("2026-04471", 0.96, 0.70, 0.12, 0.92, 0.15),
        invoice_date=f("14.07.2026", 0.72, 0.70, 0.16, 0.88, 0.19),
        due_date=f("13.08.2026", 0.55, 0.70, 0.20, 0.88, 0.23),
        currency=f("EUR", 0.9, 0.80, 0.72, 0.86, 0.75),
        net_amount=f("1.234,00", 0.88, 0.78, 0.66, 0.92, 0.69),
        vat_amount=f("234,46", 0.62, 0.78, 0.69, 0.92, 0.72),
        total_amount=f("1.468,46", 0.9, 0.78, 0.73, 0.92, 0.77),
        vat_number=f("DE811907980", 0.8, 0.06, 0.88, 0.30, 0.91),
        payment_reference=f("1234567890128", 0.7, 0.30, 0.82, 0.55, 0.85),
        iban=f("DE89 3704 0044 0532 0130 00", 0.85, 0.06, 0.80, 0.48, 0.83),
        po_reference=f("PO-88123", 0.5, 0.06, 0.60, 0.26, 0.63),
    )
