"""Generate a batch of realistic, *varied* sample invoices for the demo.

Each invoice is rendered from a data record, and the renderer records the exact
bounding box (normalised 0-1) of every value it draws. Those boxes become the
"ground truth" the mock extractor returns - so in mock mode each invoice opens
with its own supplier, amounts and line items, and the overlay boxes still land
on the right words.

Some invoices are deliberately imperfect (a bank in a different country from the
supplier, a bad payment-reference check digit, line items that don't sum to the
net, missing fields) so the verification screen shows the full range of states.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from stdnum import iban as _iban
from stdnum import luhn
from stdnum.eu import vat as _eu_vat

W, H = 1240, 1754
MARGIN = 90

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
BOLD_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def _font(size, bold=False):
    for p in (BOLD_CANDIDATES if bold else []) + FONT_CANDIDATES:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


# ---- valid identifier helpers ----

def _make_iban(cc: str, bban: str) -> str:
    def to_num(s):
        return "".join(str(int(ch, 36)) for ch in s)
    check = 98 - int(to_num(bban + cc + "00")) % 97
    return f"{cc}{check:02d}{bban}"


_BBAN = {"DE": 18, "SE": 20, "DK": 14, "FI": 14, "BE": 12, "AT": 16}


def _rand_iban(cc: str, rng: random.Random) -> str:
    if cc == "NL":
        bban = "ABNA" + f"{rng.randint(0, 10**10 - 1):010d}"
    elif cc == "IT":
        bban = "X" + f"{rng.randint(0, 10**22 - 1):022d}"
    else:
        n = _BBAN[cc]
        bban = f"{rng.randint(0, 10**n - 1):0{n}d}"
    return _make_iban(cc, bban)


def _valid_vat(cc: str, rng: random.Random) -> str:
    for _ in range(40000):
        if cc == "AT":
            body = "U" + f"{rng.randint(0, 10**8 - 1):08d}"
        elif cc == "NL":
            body = f"{rng.randint(0, 10**9 - 1):09d}B{rng.randint(1, 99):02d}"
        elif cc == "BE":
            body = f"0{rng.randint(0, 10**9 - 1):09d}"
        elif cc == "SE":
            body = f"{rng.randint(0, 10**10 - 1):010d}01"
        elif cc == "IT":
            body = f"{rng.randint(0, 10**11 - 1):011d}"
        elif cc in ("DK", "FI"):
            body = f"{rng.randint(0, 10**8 - 1):08d}"
        else:  # DE
            body = f"{rng.randint(0, 10**9 - 1):09d}"
        num = cc + body
        if _eu_vat.is_valid(num):
            return num
    return cc + "000000000"


def _luhn(rng: random.Random, valid: bool = True) -> str:
    base = "".join(str(rng.randint(0, 9)) for _ in range(rng.choice([9, 11])))
    ref = base + luhn.calc_check_digit(base)
    if not valid:  # break the check digit
        last = (int(ref[-1]) + 1) % 10
        ref = ref[:-1] + str(last)
    return ref


def _eur(n) -> str:
    s = f"{n:,.2f}"                       # 1,234.56
    return s.replace(",", " ").replace(".", ",").replace(" ", ".")  # 1.234,56


# ---- suppliers ----

@dataclass
class Supplier:
    name: str
    country: str
    city: str
    currency: str
    vat_rate: int
    vat: str = ""
    iban: str = ""


_SUPPLIER_SEED = [
    ("Nordwind Logistik GmbH", "DE", "Hamburg", "EUR", 19),
    ("Rheinbau Bürotechnik AG", "DE", "Köln", "EUR", 19),
    ("Van der Berg Transport BV", "NL", "Rotterdam", "EUR", 21),
    ("Amstel Supplies BV", "NL", "Amsterdam", "EUR", 21),
    ("Ardenne Services SA", "BE", "Liège", "EUR", 21),
    ("Alpen Handel GmbH", "AT", "Graz", "EUR", 20),
    ("Suomi Tech Oy", "FI", "Helsinki", "EUR", 24),
    ("Milano Forniture SrL", "IT", "Milano", "EUR", 22),
    ("København Data ApS", "DK", "København", "DKK", 25),
    ("Göteborg Frakt AB", "SE", "Göteborg", "SEK", 25),
]

_LINE_CATALOG = [
    ("Freight forwarding", 480, 1290),
    ("Customs handling fee", 90, 260),
    ("Fuel surcharge", 120, 340),
    ("Pallet & packaging", 45, 180),
    ("Warehousing, monthly", 300, 900),
    ("Consulting, per day", 650, 1200),
    ("Software licence, annual", 400, 2400),
    ("On-site support", 220, 700),
    ("Spare parts", 60, 480),
    ("Express delivery", 75, 250),
]


def _suppliers(rng: random.Random) -> list[Supplier]:
    out = []
    foreign = ["SE", "DK", "PL" if False else "NL"]  # for fraud demos, length-safe
    for i, (name, cc, city, cur, rate) in enumerate(_SUPPLIER_SEED):
        s = Supplier(name, cc, city, cur, rate)
        s.vat = _valid_vat(cc, rng)
        s.iban = _rand_iban(cc, rng)
        out.append(s)
    return out


# ---- record + render ----

@dataclass
class Record:
    supplier: Supplier
    number: str
    inv_date: str
    due_date: str
    lines: list[tuple[str, str, str]]  # (desc, unit, amount) qty always 1
    net: float
    vat: float
    total: float
    iban: str
    bic: str
    payment_ref: str
    po: str
    problems: list[str] = field(default_factory=list)
    printed_net: float = 0.0


def build_records(n: int, seed: int = 7) -> list[Record]:
    rng = random.Random(seed)
    suppliers = _suppliers(rng)
    records: list[Record] = []
    base_day = date(2026, 7, 1)
    for i in range(n):
        s = suppliers[i % len(suppliers)]
        k = rng.randint(1, 4)
        lines = []
        net = 0.0
        for _ in range(k):
            desc, lo, hi = rng.choice(_LINE_CATALOG)
            amt = round(rng.uniform(lo, hi), 2)
            net += amt
            lines.append((desc, _eur(amt), _eur(amt)))
        net = round(net, 2)
        vat = round(net * s.vat_rate / 100.0, 2)
        total = round(net + vat, 2)

        problems: list[str] = []
        iban = s.iban
        if i % 8 == 3:  # fraudulent: bank in a different country
            foreign = "SE" if s.country != "SE" else "DK"
            iban = _rand_iban(foreign, rng)
            problems.append("country_mismatch")
        pay = _luhn(rng, valid=not (i % 8 == 5))
        if i % 8 == 5:
            problems.append("bad_ref")
        printed_net = net
        if i % 9 == 4:  # line items won't reconcile to the printed net
            printed_net = round(net + rng.uniform(20, 90), 2)
            total = round(printed_net + vat, 2)
            problems.append("rows_mismatch")
        po = "" if i % 3 == 0 else f"PO-{rng.randint(10000, 99999)}"
        pay_field = pay if i % 11 != 7 else ""
        if not pay_field:
            problems.append("no_ref")

        inv = base_day + timedelta(days=rng.randint(0, 45))
        due = inv + timedelta(days=30)
        records.append(Record(
            supplier=s,
            number=f"{inv.year}-{4000 + i}",
            inv_date=inv.strftime("%d.%m.%Y"),
            due_date=due.strftime("%d.%m.%Y"),
            lines=lines, net=net, vat=vat, total=total,
            iban=iban, bic="COBADEFFXXX",
            payment_ref=pay_field, po=po,
            problems=problems, printed_net=printed_net,
        ))
    return records


def render(rec: Record):
    """Draw the invoice and return (PIL image, truth dict with normalised boxes)."""
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    ink, grey, line = (25, 30, 40), (110, 118, 128), (200, 206, 214)

    def draw(x, y, s, f, fill=ink):
        d.text((x, y), s, font=f, fill=fill)
        x0, y0, x1, y1 = d.textbbox((x, y), s, font=f)
        return [x0 / W, y0 / H, x1 / W, y1 / H]

    fields: dict[str, dict] = {}

    def fld(key, box, value, conf=0.95):
        fields[key] = {"value": value, "confidence": conf, "box": box, "found": True}

    s = rec.supplier
    fld("supplier_name", draw(MARGIN, 90, s.name, _font(32, bold=True)), s.name, 0.97)
    draw(MARGIN, 138, f"{s.city}, {s.country}", _font(20), grey)
    fld("vat_number", draw(MARGIN, 166, f"VAT {s.vat}", _font(20), grey), s.vat, 0.85)

    draw(760, 90, "INVOICE", _font(40, bold=True))
    y = 150
    fld("invoice_number", draw(980, y, rec.number, _font(20, bold=True)), rec.number, 0.96)
    draw(760, y, "Invoice number", _font(18), grey); y += 34
    fld("invoice_date", draw(980, y, rec.inv_date, _font(20, bold=True)), rec.inv_date, 0.9)
    draw(760, y, "Invoice date", _font(18), grey); y += 34
    fld("due_date", draw(980, y, rec.due_date, _font(20, bold=True)), rec.due_date, 0.55)
    draw(760, y, "Due date", _font(18), grey)

    draw(MARGIN, 300, "Bill to  Kase Technologies AB, Stockholm, Sweden", _font(20), grey)

    top = 430
    d.line([(MARGIN, top), (W - MARGIN, top)], fill=line, width=2)
    draw(MARGIN, top + 14, "Description", _font(18, bold=True), grey)
    draw(1010, top + 14, "Amount", _font(18, bold=True), grey)
    d.line([(MARGIN, top + 44), (W - MARGIN, top + 44)], fill=line, width=2)

    items = []
    ry = top + 60
    for desc, unit, amt in rec.lines:
        draw(MARGIN, ry, desc, _font(20))
        draw(1010, ry, amt, _font(20))
        items.append({
            "description": desc, "quantity": "1", "unit_price": unit, "amount": amt,
            "confidence": 0.9,
            "box": [MARGIN / W, (ry - 3) / H, (W - MARGIN) / W, (ry + 27) / H],
        })
        ry += 40

    ty = ry + 24
    draw(820, ty, "Net amount", _font(20), grey)
    fld("net_amount", draw(1010, ty, _eur(rec.printed_net), _font(20)), _eur(rec.printed_net), 0.88)
    ty += 34
    draw(820, ty, f"VAT {s.vat_rate}%", _font(20), grey)
    fld("vat_amount", draw(1010, ty, _eur(rec.vat), _font(20)), _eur(rec.vat), 0.7)
    ty += 40
    fld("total_amount", draw(1010, ty, _eur(rec.total), _font(24, bold=True)), _eur(rec.total), 0.92)
    draw(820, ty, f"Total {s.currency}", _font(24, bold=True))
    fld("currency", [820 / W, (ty + 6) / H, 900 / W, (ty + 28) / H], s.currency, 0.9)

    py = ty + 110
    draw(MARGIN, py, "Payment details", _font(20, bold=True))
    yy = py + 36
    fld("iban", draw(430, yy, rec.iban, _font(19)), rec.iban, 0.85)
    draw(MARGIN, yy, "IBAN", _font(19), grey); yy += 30
    draw(MARGIN, yy, "BIC", _font(19), grey)
    draw(430, yy, rec.bic, _font(19)); yy += 30
    if rec.payment_ref:
        fld("payment_reference", draw(430, yy, rec.payment_ref, _font(19)), rec.payment_ref, 0.7)
        draw(MARGIN, yy, "Payment reference (OCR)", _font(19), grey); yy += 30
    if rec.po:
        fld("po_reference", draw(430, yy, rec.po, _font(19)), rec.po, 0.6)
        draw(MARGIN, yy, "Your order / PO", _font(19), grey)

    truth = {"fields": fields, "line_items": items}
    return img, truth
