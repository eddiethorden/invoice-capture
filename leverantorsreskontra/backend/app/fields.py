"""The canonical set of invoice fields the system reads and verifies.

This list is the contract between the extraction model, the validation logic,
and the verification screen. Keep it in sync with the frontend field metadata.
"""

# key, visningsetikett (svenska), informativ ledtråd
FIELD_DEFS = [
    ("supplier_name", "Leverantör", "Leverantör"),
    ("invoice_number", "Fakturanummer", "Fakturanummer"),
    ("invoice_date", "Fakturadatum", "Fakturadatum"),
    ("due_date", "Förfallodatum", "Förfallodatum"),
    ("currency", "Valuta", "Valuta"),
    ("net_amount", "Nettobelopp", "Nettobelopp"),
    ("vat_amount", "Moms", "Moms"),
    ("total_amount", "Totalt", "Totalt"),
    ("vat_number", "Momsreg.nr", "Momsreg.nr"),
    ("payment_reference", "Betalreferens (OCR)", "Betalreferens (OCR)"),
    ("iban", "IBAN / bankkonto", "Bankkonto"),
    ("bankgiro", "Bankgiro", "Bankgiro"),
    ("plusgiro", "Plusgiro", "Plusgiro"),
    ("po_reference", "Projekt / order", "Projekt / order"),
]

FIELD_KEYS = [f[0] for f in FIELD_DEFS]
FIELD_LABELS = {f[0]: f[1] for f in FIELD_DEFS}

# Fields that participate in the net + VAT = total arithmetic check.
AMOUNT_FIELDS = ("net_amount", "vat_amount", "total_amount")
