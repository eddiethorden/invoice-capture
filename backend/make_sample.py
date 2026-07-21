"""Generate a realistic synthetic supplier invoice PDF for testing extraction.

Deliberately European: '1.234,56' number formatting, a German supplier with a
VAT reg number and IBAN, a Swedish OCR payment reference, and a PO number - so
it exercises locale parsing and the full field set.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1240, 1754  # ~A4 at 150 dpi
MARGIN = 90

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def font(size: int, bold: bool = False):
    paths = FONT_CANDIDATES
    if bold:
        paths = [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ] + paths
    for p in paths:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def main() -> None:
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)

    ink = (25, 30, 40)
    grey = (110, 118, 128)
    line = (200, 206, 214)

    F = lambda s: font(s)
    B = lambda s: font(s, bold=True)

    # --- Supplier header ---
    d.text((MARGIN, 90), "Nordwind Logistik GmbH", font=B(34), fill=ink)
    d.text((MARGIN, 138), "Speicherstrasse 12, 20457 Hamburg, Germany", font=F(20), fill=grey)
    d.text((MARGIN, 166), "USt-IdNr: DE811907980", font=F(20), fill=grey)

    # --- Invoice meta (right) ---
    d.text((760, 90), "INVOICE", font=B(40), fill=ink)
    meta = [
        ("Invoice number", "2026-04471"),
        ("Invoice date", "14.07.2026"),
        ("Due date", "13.08.2026"),
    ]
    y = 150
    for label, value in meta:
        d.text((760, y), label, font=F(18), fill=grey)
        d.text((980, y), value, font=B(20), fill=ink)
        y += 34

    # --- Bill to ---
    d.text((MARGIN, 280), "Bill to", font=B(18), fill=grey)
    d.text((MARGIN, 306), "Kase Technologies AB", font=F(22), fill=ink)
    d.text((MARGIN, 336), "Regeringsgatan 25, 111 53 Stockholm, Sweden", font=F(20), fill=grey)

    # --- Line items ---
    top = 430
    d.line([(MARGIN, top), (W - MARGIN, top)], fill=line, width=2)
    d.text((MARGIN, top + 14), "Description", font=B(18), fill=grey)
    d.text((720, top + 14), "Qty", font=B(18), fill=grey)
    d.text((820, top + 14), "Unit price", font=B(18), fill=grey)
    d.text((1010, top + 14), "Amount", font=B(18), fill=grey)
    d.line([(MARGIN, top + 44), (W - MARGIN, top + 44)], fill=line, width=2)

    rows = [
        ("Freight forwarding, Hamburg - Stockholm", "1", "890,00", "890,00"),
        ("Customs handling fee", "1", "120,00", "120,00"),
        ("Fuel surcharge", "1", "224,00", "224,00"),
    ]
    y = top + 60
    for desc, qty, unit, amt in rows:
        d.text((MARGIN, y), desc, font=F(20), fill=ink)
        d.text((730, y), qty, font=F(20), fill=ink)
        d.text((820, y), unit, font=F(20), fill=ink)
        d.text((1010, y), amt, font=F(20), fill=ink)
        y += 40

    # --- Totals ---
    ty = y + 30
    totals = [
        ("Net amount", "1.234,00"),
        ("VAT 19%", "234,46"),
    ]
    for label, value in totals:
        d.text((820, ty), label, font=F(20), fill=grey)
        d.text((1010, ty), value, font=F(20), fill=ink)
        ty += 34
    d.line([(820, ty + 4), (W - MARGIN, ty + 4)], fill=line, width=2)
    ty += 16
    d.text((820, ty), "Total EUR", font=B(24), fill=ink)
    d.text((1010, ty), "1.468,46", font=B(24), fill=ink)

    # --- Payment details ---
    py = ty + 120
    d.text((MARGIN, py), "Payment details", font=B(20), fill=ink)
    pay = [
        ("IBAN", "DE89 3704 0044 0532 0130 00"),
        ("BIC", "COBADEFFXXX"),
        ("Payment reference (OCR)", "1234567890128"),
        ("Your order / PO", "PO-88123"),
    ]
    yy = py + 36
    for label, value in pay:
        d.text((MARGIN, yy), label, font=F(19), fill=grey)
        d.text((430, yy), value, font=F(19), fill=ink)
        yy += 30

    d.text((MARGIN, H - 90), "Reverse charge does not apply. VAT charged at German standard rate.",
           font=F(16), fill=grey)

    out = Path(__file__).parent / "samples" / "sample_invoice.pdf"
    out.parent.mkdir(exist_ok=True)
    img.save(out, "PDF", resolution=150.0)
    img.save(out.with_suffix(".png"))
    print("wrote", out)


if __name__ == "__main__":
    main()
