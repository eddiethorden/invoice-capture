"""Render the system description + mini manual markdown into one PDF.

    backend/.venv/bin/python docs/make_manual_pdf.py

A small markdown subset is supported: # / ## / ### headings, paragraphs,
- bullets, | tables |, and ``` code blocks. Inline **bold** is rendered.
"""

from __future__ import annotations

import re
from pathlib import Path

from fpdf import FPDF
from fpdf.fonts import FontFace
from PIL import Image as PILImage

HERE = Path(__file__).resolve().parent
FILES = [HERE / "SYSTEM_DESCRIPTION.md", HERE / "MINI_MANUAL.md"]
OUT = HERE / "system_overview_and_manual.pdf"

NAVY = (36, 41, 47)
BLUE = (9, 105, 218)
GREY = (101, 109, 118)
LIGHT = (246, 248, 250)

_SUBST = {
    "—": "-", "–": "-", "·": " - ", "→": "->", "←": "<-", "▶": ">", "▼": "v",
    "│": "|", "├": "+", "└": "+", "┌": "+", "┐": "+", "┘": "+", "─": "-",
    "⌘": "Cmd", "✓": "(ok)", "✕": "x", "⚠": "!", "…": "...", "€": "EUR",
    "≥": ">=", "×": "x", "“": '"', "”": '"', "‘": "'", "’": "'", " ": " ",
}


def san(s: str) -> str:
    for a, b in _SUBST.items():
        s = s.replace(a, b)
    return s.encode("latin-1", "replace").decode("latin-1")


def parse(md: str):
    blocks, para, table, code = [], [], [], []
    in_code = False
    for raw in md.splitlines():
        line = raw.rstrip("\n")
        if line.strip().startswith("```"):
            if in_code:
                blocks.append(("code", code)); code = []
            in_code = not in_code
            continue
        if in_code:
            code.append(line); continue

        is_table = line.strip().startswith("|")
        img_m = re.fullmatch(r"!\[(.*)\]\((.+)\)", line.strip())
        if table and not is_table:
            blocks.append(("table", table)); table = []
        if para and (not line.strip() or line.startswith("#")
                     or line.startswith("- ") or is_table or img_m):
            blocks.append(("para", " ".join(para))); para = []

        if is_table:
            table.append(line); continue
        if img_m:
            blocks.append(("image", (img_m.group(2), img_m.group(1)))); continue
        if not line.strip():
            continue
        if line.startswith("### "):
            blocks.append(("h3", line[4:]))
        elif line.startswith("## "):
            blocks.append(("h2", line[3:]))
        elif line.startswith("# "):
            blocks.append(("h1", line[2:]))
        elif line.startswith("- "):
            blocks.append(("bullet", line[2:]))
        else:
            para.append(line.strip())
    if para:
        blocks.append(("para", " ".join(para)))
    if table:
        blocks.append(("table", table))
    return blocks


def render_table(pdf, W, rows):
    cells = [[san(c.strip()) for c in r.strip().strip("|").split("|")] for r in rows]
    # drop the |---| separator row
    cells = [r for r in cells if not all(re.fullmatch(r":?-{2,}:?", c) for c in r)]
    if not cells:
        return
    pdf.ln(1)
    pdf.set_font("Helvetica", "", 9)      # body cell style (headers overridden below)
    pdf.set_text_color(*NAVY)
    heading = FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=NAVY)
    with pdf.table(width=W, markdown=True, text_align="LEFT",
                   headings_style=heading) as table:
        for r in cells:
            row = table.row()
            for c in r:
                row.cell(c)
    pdf.ln(1)


def render_image(pdf, W, rel_path, caption):
    path = HERE / rel_path
    if not path.exists():
        return
    iw, ih = PILImage.open(path).size
    max_h = 165  # mm — leave room for heading/caption on the page
    disp_w, disp_h = W, W * ih / iw
    if disp_h > max_h:
        disp_h, disp_w = max_h, max_h * iw / ih
    if pdf.get_y() + disp_h + 14 > pdf.h - pdf.b_margin:
        pdf.add_page()
    x = pdf.l_margin + (W - disp_w) / 2
    y = pdf.get_y()
    pdf.image(str(path), x=x, y=y, w=disp_w, h=disp_h)
    pdf.set_draw_color(208, 215, 222)
    pdf.set_line_width(0.2)
    pdf.rect(x, y, disp_w, disp_h)
    pdf.set_y(y + disp_h + 2)
    if caption:
        pdf.set_font("Helvetica", "I", 8.5)
        pdf.set_text_color(*GREY)
        pdf.multi_cell(W, 4.5, san(caption), align="C")
    pdf.ln(3)


def render(pdf, W, blocks):
    for kind, payload in blocks:
        if kind == "h1":
            pdf.ln(1); pdf.set_font("Helvetica", "B", 16); pdf.set_text_color(*NAVY)
            pdf.multi_cell(W, 8, san(payload)); pdf.ln(1)
            pdf.set_draw_color(*BLUE); pdf.set_line_width(0.4)
            y = pdf.get_y(); pdf.line(pdf.l_margin, y, pdf.l_margin + W, y); pdf.ln(3)
        elif kind == "h2":
            pdf.ln(2); pdf.set_font("Helvetica", "B", 13); pdf.set_text_color(*BLUE)
            pdf.multi_cell(W, 6, san(payload)); pdf.ln(1)
        elif kind == "h3":
            pdf.ln(1); pdf.set_font("Helvetica", "B", 11); pdf.set_text_color(*NAVY)
            pdf.multi_cell(W, 5.5, san(payload)); pdf.ln(0.5)
        elif kind == "para":
            pdf.set_font("Helvetica", "", 10); pdf.set_text_color(*NAVY)
            pdf.multi_cell(W, 5, san(payload), markdown=True); pdf.ln(1.5)
        elif kind == "bullet":
            pdf.set_font("Helvetica", "", 10); pdf.set_text_color(*NAVY)
            x = pdf.get_x()
            pdf.set_text_color(*BLUE); pdf.cell(5, 5, chr(149))
            pdf.set_text_color(*NAVY)
            pdf.multi_cell(W - 5, 5, san(payload), markdown=True, new_x="LMARGIN")
            pdf.set_x(x); pdf.ln(0.5)
        elif kind == "code":
            pdf.ln(1); pdf.set_font("Courier", "", 8.5); pdf.set_text_color(*NAVY)
            pdf.set_fill_color(*LIGHT)
            for ln in payload:
                pdf.cell(W, 4.4, "  " + san(ln), fill=True, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
        elif kind == "table":
            render_table(pdf, W, payload)
        elif kind == "image":
            render_image(pdf, W, payload[0], payload[1])


def main():
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.set_margins(16, 15, 16)
    W = 210 - 32
    for i, f in enumerate(FILES):
        pdf.add_page()
        render(pdf, W, parse(f.read_text()))
    pdf.output(str(OUT))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
