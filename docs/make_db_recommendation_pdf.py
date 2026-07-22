"""Generate a client-facing PDF: the database recommendation and reasoning.

Vector text (selectable) via fpdf2. Run with the backend venv:
    backend/.venv/bin/python docs/make_db_recommendation_pdf.py
"""

from pathlib import Path

from fpdf import FPDF

NAVY = (36, 41, 47)
BLUE = (9, 105, 218)
GREY = (101, 109, 118)
LINE = (208, 215, 222)
LIGHT = (246, 248, 250)

L = 18
CONTENT_W = 210 - 2 * L


class Doc(FPDF):
    def heading(self, text):
        self.ln(2)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(*BLUE)
        self.set_x(L)
        self.multi_cell(CONTENT_W, 6, text)
        self.ln(0.5)

    def para(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*NAVY)
        self.set_x(L)
        self.multi_cell(CONTENT_W, 5, text)
        self.ln(1.5)

    def bullets(self, items):
        self.set_font("Helvetica", "", 10)
        for head, body in items:
            y = self.get_y()
            self.set_xy(L + 1, y)
            self.set_text_color(*BLUE)
            self.cell(4, 5, chr(149))
            self.set_x(L + 5)
            self.set_text_color(*NAVY)
            self.set_font("Helvetica", "B", 10)
            self.write(5, head + "  ")
            self.set_font("Helvetica", "", 10)
            self.set_text_color(*GREY)
            self.multi_cell(CONTENT_W - 5, 5, body, new_x="LMARGIN")
            self.ln(0.5)
        self.ln(1.5)


def make() -> Path:
    pdf = Doc(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()
    pdf.set_margins(L, 16, L)

    # Title
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 9, "Storing Incoming Invoices", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*GREY)
    pdf.cell(0, 6, "Database recommendation  -  Automated Invoice Capture", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    pdf.set_draw_color(*LINE)
    pdf.set_line_width(0.3)
    y = pdf.get_y()
    pdf.line(L, y, L + CONTENT_W, y)
    pdf.ln(3)

    pdf.para(
        "This note sets out our recommendation for where incoming supplier invoices "
        "should be stored, and the reasoning behind it. Two facts about your setup "
        "shape the answer:"
    )
    pdf.bullets([
        ("Volume and users.", "Up to around 1,000 invoices per day, with at most two "
         "people verifying them at any one time."),
        ("Marathon is the destination.", "The approved, coded invoice is delivered "
         "into Marathon, which remains the system of record."),
    ])

    pdf.heading("The key point")
    pdf.para(
        "Because the approved invoice lives in Marathon - with Marathon's approval "
        "chain, purchase ledger and long-term retention - the capture system's own "
        "database does not need to be a permanent archive. It is a working store: it "
        "holds each invoice while it is read and verified, delivers it to Marathon, and "
        "keeps a small amount of data to catch duplicates and to read each supplier's "
        "layout better over time. The obligations of immutable, long-term, audited "
        "storage sit with Marathon, not with us."
    )

    pdf.heading("Our recommendation: SQLite")
    pdf.para(
        "We recommend SQLite - a small, proven database that runs inside the "
        "application itself, with no separate database server to install, run, secure "
        "or back up. For a focused internal tool of this size it is the simplest option "
        "that fully does the job."
    )
    pdf.bullets([
        ("Comfortably within its limits.", "Around 1,000 invoices a day is a small "
         "fraction of what SQLite handles."),
        ("Two users is no concern.", "It easily supports the few people and background "
         "tasks involved."),
        ("Fewer moving parts.", "No database server means less to maintain, less to go "
         "wrong, and lower running cost."),
        ("Trivial backup.", "The whole database is a single file that can be copied or "
         "continuously mirrored offsite."),
        ("Search built in.", "Full-text search across invoice contents, with no extra "
         "software."),
    ])

    pdf.heading("What we store, and for how long")
    pdf.para(
        "Because Marathon holds the permanent record, the capture database stays small. "
        "Once an invoice has been safely delivered to Marathon we keep it for a short "
        "reference period - for example 30 to 90 days - and then remove the invoice "
        "content, retaining only a small fingerprint (so the same invoice can never be "
        "paid twice) and the learning data that makes future invoices faster to process."
    )

    pdf.heading("One practical requirement")
    pdf.para(
        "SQLite runs on the application server's own local disk, not on a shared network "
        "drive. This is a standard requirement and simply guides where the software is "
        "installed."
    )

    pdf.heading("A considered choice, not a limitation")
    pdf.para(
        "For large, multi-server systems the industry-standard database is PostgreSQL. "
        "We have kept the design so that moving to PostgreSQL later - should volumes or "
        "the number of users grow substantially - is a straightforward migration rather "
        "than a rewrite. Choosing SQLite now therefore commits you to nothing."
    )

    _table(pdf, [
        ("", "SQLite  (recommended)", "PostgreSQL"),
        ("Setup & operation", "Runs inside the app; nothing to run", "Separate server to run & secure"),
        ("Best suited to", "Focused tool, a few users", "Many users / multiple servers"),
        ("Backup", "Copy a single file", "Managed backups"),
        ("For this project", "Ideal fit", "More than needed today"),
    ])

    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*NAVY)
    pdf.set_x(L)
    pdf.multi_cell(CONTENT_W, 5,
        "In short: SQLite gives you a simpler, lower-maintenance system that fully meets "
        "today's needs, with a clear path to PostgreSQL preserved should you ever need it.")

    out = Path(__file__).parent / "database_recommendation.pdf"
    pdf.output(str(out))
    return out


def _table(pdf, rows):
    widths = [40, 68, CONTENT_W - 40 - 68]
    pdf.ln(1)
    for i, row in enumerate(rows):
        y = pdf.get_y()
        header = i == 0
        if header:
            pdf.set_fill_color(*NAVY)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Helvetica", "B", 9)
        else:
            if i % 2 == 0:
                pdf.set_fill_color(*LIGHT)
                pdf.rect(L, y, CONTENT_W, 6, style="F")
            pdf.set_text_color(*NAVY)
            pdf.set_font("Helvetica", "", 9)
        if header:
            pdf.rect(L, y, CONTENT_W, 6, style="F")
        x = L
        for w, cell in zip(widths, row):
            pdf.set_xy(x + 1.5, y)
            pdf.cell(w - 1.5, 6, cell)
            x += w
        pdf.set_y(y + 6)


if __name__ == "__main__":
    print("wrote", make())
