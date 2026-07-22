"""Generate a one-page A4 PDF describing the technology stack.

Vector text (selectable) via fpdf2. Run with the backend venv:
    python docs/make_stack_pdf.py
"""

from pathlib import Path

from fpdf import FPDF

NAVY = (36, 41, 47)
BLUE = (9, 105, 218)
GREY = (101, 109, 118)
LINE = (208, 215, 222)
LIGHT = (246, 248, 250)

L = 15  # left margin (mm)
CONTENT_W = 210 - 2 * L


def make() -> Path:
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()
    pdf.set_margins(L, 12, L)

    # ---- Title ----
    pdf.set_xy(L, 12)
    pdf.set_font("Helvetica", "B", 17)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 8, "Automated Invoice Capture", ln=1)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*GREY)
    pdf.cell(0, 6, "Technology stack - reads supplier invoices, verifies, feeds Marathon", ln=1)
    pdf.ln(1)
    _rule(pdf)
    pdf.ln(2.5)

    # ---- Runtime flow ----
    _heading(pdf, "Runtime flow")
    pdf.set_font("Courier", "", 8.5)
    pdf.set_text_color(*NAVY)
    for line in [
        "Browser (React / Vite)  --fetch /api-->  FastAPI + Uvicorn",
        "   FastAPI  ->  pypdfium2 (PDF->PNG)  ->  Claude Opus 4.8 vision  [or mock]",
        "            ->  python-stdnum (VAT/IBAN/Luhn)  ->  filesystem store",
    ]:
        pdf.set_x(L + 2)
        pdf.cell(0, 4.6, line, ln=1)
    pdf.ln(2.5)

    # ---- Backend ----
    _heading(pdf, "Backend  -  Python 3.14")
    _table(pdf, [
        ("Web framework", "FastAPI + Uvicorn (ASGI)"),
        ("File upload", "python-multipart"),
        ("PDF -> images", "pypdfium2 (pip-only, no system deps)"),
        ("Image handling", "Pillow"),
        ("AI extraction", "anthropic SDK  ->  messages.parse (structured output)"),
        ("Schema / validation", "Pydantic v2  (the schema is the model contract)"),
        ("Country validation", "python-stdnum  (VAT, IBAN checksum, Luhn check digit)"),
        ("Money / dedup", "stdlib decimal (exact), hashlib SHA-256 (duplicate fingerprint)"),
        ("Storage", "filesystem + in-memory  (originals, page PNGs, result.json)"),
    ])
    pdf.ln(2)

    # ---- Frontend + AI side by side would be tight; stack them compactly ----
    _heading(pdf, "Frontend  -  JavaScript")
    _table(pdf, [
        ("UI library", "React 18"),
        ("Build / dev server", "Vite 6  (proxies /api -> :8000)"),
        ("Invoice rendering", "server PNG + SVG overlay, coords normalized 0-1"),
        ("Styling / HTTP", "plain CSS  /  native fetch"),
    ])
    pdf.ln(2)

    # ---- AI / model ----
    _heading(pdf, "AI / model layer")
    _bullets(pdf, [
        "Claude Opus 4.8 (claude-opus-4-8) vision - high-res boxes map 1:1 to page pixels",
        "Auth: ANTHROPIC_API_KEY / AUTH_TOKEN / ant CLI OAuth profile (SDK-resolved)",
        "Deterministic mock fallback - the whole app runs with no key/credit",
    ])
    pdf.ln(2)

    # ---- Target (not yet built) ----
    _heading(pdf, "Target stack  -  proposed (Section 4), not yet built")
    _table(pdf, [
        ("Database", "PostgreSQL 16 (typed cols + JSONB)      today: in-memory + JSON"),
        ("Object storage", "MinIO / S3                              today: local filesystem"),
        ("Invoice render (FE)", "PDF.js overlay                          today: PNG + SVG"),
        ("Text / OCR path", "pdfplumber / Poppler, OCRmyPDF/Tesseract   today: vision only"),
        ("Tax registration", "VIES online lookup                      today: structural only"),
        ("Handover", "transactional outbox -> Marathon        today: verify stores values"),
        ("Packaging", "Docker Compose / Kubernetes             today: run directly"),
    ], zebra=True)

    # ---- Footer ----
    pdf.set_y(-14)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(*GREY)
    pdf.cell(0, 4, "Stack aligns with proposal Section 4. Boxes stored normalized, so the PDF.js "
                   "swap is a front-end-only change.", align="C")

    out = Path(__file__).parent / "tech_stack.pdf"
    pdf.output(str(out))
    return out


def _rule(pdf):
    pdf.set_draw_color(*LINE)
    pdf.set_line_width(0.3)
    y = pdf.get_y()
    pdf.line(L, y, L + CONTENT_W, y)


def _heading(pdf, text):
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*BLUE)
    pdf.set_x(L)
    pdf.cell(0, 6, text, ln=1)


def _table(pdf, rows, zebra=False):
    c1 = 46
    pdf.set_font("Helvetica", "", 9)
    for i, (a, b) in enumerate(rows):
        y = pdf.get_y()
        if zebra and i % 2 == 0:
            pdf.set_fill_color(*LIGHT)
            pdf.rect(L, y, CONTENT_W, 5.4, style="F")
        pdf.set_xy(L + 1, y)
        pdf.set_text_color(*GREY)
        pdf.cell(c1, 5.4, a)
        pdf.set_xy(L + c1, y)
        pdf.set_text_color(*NAVY)
        pdf.cell(CONTENT_W - c1, 5.4, b, ln=1)


def _bullets(pdf, items):
    pdf.set_font("Helvetica", "", 9)
    for it in items:
        y = pdf.get_y()
        pdf.set_xy(L + 1, y)
        pdf.set_text_color(*BLUE)
        pdf.cell(4, 5.2, chr(149))  # bullet
        pdf.set_xy(L + 5, y)
        pdf.set_text_color(*NAVY)
        pdf.cell(0, 5.2, it, ln=1)


if __name__ == "__main__":
    print("wrote", make())
