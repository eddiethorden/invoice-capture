"""Generate architecture / pipeline diagrams as PNGs.

    backend/.venv/bin/python docs/make_diagrams.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

NAVY = (36, 41, 47)
BLUE = (9, 105, 218)
GREY = (101, 109, 118)
LIGHTBLUE = (221, 238, 255)
LIGHT = (246, 248, 250)
GREEN = (26, 127, 55)
WHITE = (255, 255, 255)

FONTS = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
BOLDS = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def font(sz, bold=False):
    for p in (BOLDS if bold else []) + FONTS:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, sz)
            except Exception:
                pass
    return ImageFont.load_default()


def center_text(d, box, lines, fnt, fill, line_h=None):
    x0, y0, x1, y1 = box
    line_h = line_h or (fnt.size + 6)
    total = len(lines) * line_h
    y = y0 + ((y1 - y0) - total) / 2
    for ln in lines:
        w = d.textlength(ln, font=fnt)
        d.text((x0 + ((x1 - x0) - w) / 2, y), ln, font=fnt, fill=fill)
        y += line_h


def box(d, xy, fill, outline, width=2, radius=16):
    d.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def harrow(d, x0, x1, y, color=GREY, w=4):
    d.line([(x0, y), (x1 - 12, y)], fill=color, width=w)
    d.polygon([(x1, y), (x1 - 16, y - 9), (x1 - 16, y + 9)], fill=color)


def varrow(d, x, y0, y1, color=GREY, w=4):
    d.line([(x, y0), (x, y1 - 12)], fill=color, width=w)
    d.polygon([(x, y1), (x - 9, y1 - 16), (x + 9, y1 - 16)], fill=color)


# --------------------------------------------------------------------------
def pipeline():
    W, H = 2500, 620
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)
    d.text((60, 44), "Automated Invoice Capture", font=font(46, bold=True), fill=NAVY)
    d.text((60, 104), "The six-stage pipeline — every step automatic except verification",
           font=font(26), fill=GREY)

    stages = [
        ("1", "Arrival", ["Watched folder", "or upload; dedup"]),
        ("2", "Reading", ["Pages rendered,", "read by vision model"]),
        ("3", "Interpretation", ["Fields + boxes", "+ confidence"]),
        ("4", "Verification", ["A person confirms", "on the screen"]),
        ("5", "Coding", ["Rows coded to", "Marathon projects"]),
        ("6", "Handover", ["Delivered to", "Marathon, once"]),
    ]
    m, gap, top, h = 50, 26, 210, 250
    bw = (W - 2 * m - (len(stages) - 1) * gap) / len(stages)
    for i, (num, name, desc) in enumerate(stages):
        x0 = m + i * (bw + gap)
        x1 = x0 + bw
        manual = i == 3
        box(d, (x0, top, x1, top + h),
            fill=LIGHTBLUE if manual else LIGHT,
            outline=BLUE if manual else (200, 206, 214),
            width=4 if manual else 2)
        # number chip
        d.ellipse((x0 + 24, top + 24, x0 + 78, top + 78),
                  fill=BLUE if manual else NAVY)
        cw = d.textlength(num, font=font(34, bold=True))
        d.text((x0 + 51 - cw / 2, top + 34), num, font=font(34, bold=True), fill=WHITE)
        d.text((x0 + 96, top + 34), name, font=font(30, bold=True), fill=NAVY)
        yy = top + 104
        for ln in desc:
            d.text((x0 + 30, yy), ln, font=font(23), fill=GREY)
            yy += 34
        if manual:
            d.text((x0 + 30, top + h + 14), "the only manual step",
                   font=font(21, bold=True), fill=BLUE)
        if i < len(stages) - 1:
            harrow(d, x1 + 3, x1 + gap - 3, top + h / 2)

    img.save(OUT / "05_pipeline.png")
    print("wrote 05_pipeline.png")


# --------------------------------------------------------------------------
def architecture():
    W, H = 2000, 1480
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)
    d.text((60, 44), "Architecture", font=font(46, bold=True), fill=NAVY)
    cx = W / 2

    def cbox(cx, y, w, h, title, sub, fill=LIGHT, outline=(200, 206, 214), tcol=NAVY):
        box(d, (cx - w / 2, y, cx + w / 2, y + h), fill=fill, outline=outline, width=3)
        center_text(d, (cx - w / 2, y, cx + w / 2, y + h),
                    [title] + sub, font(26, bold=True), tcol)
        # subtitle smaller
        return y + h

    # Browser
    box(d, (cx - 260, 150, cx + 260, 260), fill=NAVY, outline=NAVY, width=2)
    center_text(d, (cx - 260, 150, cx + 260, 260),
                ["Browser  ·  React / Vite"], font(30, bold=True), WHITE)
    varrow(d, cx, 260, 330)
    d.text((cx + 14, 280), "/api", font=font(22), fill=GREY)

    # FastAPI core
    box(d, (cx - 320, 330, cx + 320, 470), fill=LIGHTBLUE, outline=BLUE, width=4)
    center_text(d, (cx - 320, 330, cx + 320, 470),
                ["FastAPI + Uvicorn", "the pipeline: read - validate - store"],
                font(30, bold=True), NAVY, line_h=44)

    # workers left/right
    box(d, (120, 340, 520, 460), fill=LIGHT, outline=(200, 206, 214), width=3)
    center_text(d, (120, 340, 520, 460),
                ["Intake worker", "watched folder (poll)"], font(24, bold=True), NAVY, 40)
    harrow(d, 520, cx - 320, 400)

    box(d, (W - 520, 340, W - 120, 460), fill=LIGHT, outline=(200, 206, 214), width=3)
    center_text(d, (W - 520, 340, W - 120, 460),
                ["Outbox worker", "delivery + retries"], font(24, bold=True), NAVY, 40)
    harrow(d, cx + 320, W - 520, 400)

    # side inputs feeding the core (vision + validators)
    box(d, (120, 560, 520, 690), fill=LIGHT, outline=(200, 206, 214), width=3)
    center_text(d, (120, 560, 520, 690),
                ["Vision model", "Claude Opus 4.8", "(mock fallback)"], font(23, bold=True), NAVY, 36)
    box(d, (W - 520, 560, W - 120, 690), fill=LIGHT, outline=(200, 206, 214), width=3)
    center_text(d, (W - 520, 560, W - 120, 690),
                ["Validators", "python-stdnum", "VAT / IBAN / Luhn"], font(23, bold=True), NAVY, 36)
    d.line([(320, 560), (320, 470), (cx - 320, 470)], fill=GREY, width=3)
    d.line([(W - 320, 560), (W - 320, 470), (cx + 320, 470)], fill=GREY, width=3)

    # store row
    varrow(d, cx, 470, 760)
    d.text((cx + 14, 700), "store", font=font(22), fill=GREY)
    box(d, (cx - 620, 760, cx - 40, 900), fill=LIGHT, outline=(200, 206, 214), width=3)
    center_text(d, (cx - 620, 760, cx - 40, 900),
                ["SQLite (WAL, STRICT)", "invoices · fields · line_items", "audit · outbox"],
                font(23, bold=True), NAVY, 36)
    box(d, (cx + 40, 760, cx + 620, 900), fill=LIGHT, outline=(200, 206, 214), width=3)
    center_text(d, (cx + 40, 760, cx + 620, 900),
                ["Filesystem", "original PDFs", "+ page images"], font(23, bold=True), NAVY, 36)

    # Marathon
    box(d, (W - 620, 1060, W - 120, 1200), fill=(234, 255, 234), outline=GREEN, width=4)
    center_text(d, (W - 620, 1060, W - 120, 1200),
                ["Marathon", "(system of record)"], font(28, bold=True), GREEN, 44)
    # outbox -> marathon
    d.line([(W - 320, 460), (W - 320, 1060)], fill=GREEN, width=4)
    varrow(d, W - 320, 1000, 1060, color=GREEN)
    d.text((W - 300, 720), "transactional outbox", font=font(22, bold=True), fill=GREEN)
    d.text((W - 300, 752), "idempotent · retries", font=font(20), fill=GREY)

    img.save(OUT / "06_architecture.png")
    print("wrote 06_architecture.png")


if __name__ == "__main__":
    pipeline()
    architecture()
    print("diagrams in", OUT)
