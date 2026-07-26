"""The canonical set of invoice fields the system reads and verifies.

This list is the contract between the extraction model, the validation logic,
and the verification screen. Keep it in sync with the frontend field metadata.
"""

# key, human label, Swedish/Marathon hint (informational)
FIELD_DEFS = [
    ("supplier_name", "Supplier", "Leverantör"),
    ("invoice_number", "Invoice number", "Fakturanummer"),
    ("invoice_date", "Invoice date", "Fakturadatum"),
    ("due_date", "Due date", "Förfallodatum"),
    ("currency", "Currency", "Valuta"),
    ("net_amount", "Net", "Nettobelopp"),
    ("vat_amount", "VAT", "Moms"),
    ("total_amount", "Total", "Totalt"),
    ("vat_number", "VAT reg. no.", "Momsreg.nr"),
    ("payment_reference", "Payment reference", "Betalreferens (OCR)"),
    ("iban", "IBAN / bank account", "Bankkonto"),
    ("bankgiro", "Bankgiro", "Bankgiro"),
    ("plusgiro", "Plusgiro", "Plusgiro"),
    ("po_reference", "PO / project reference", "Projekt / order"),
]

FIELD_KEYS = [f[0] for f in FIELD_DEFS]
FIELD_LABELS = {f[0]: f[1] for f in FIELD_DEFS}

# Fields that participate in the net + VAT = total arithmetic check.
AMOUNT_FIELDS = ("net_amount", "vat_amount", "total_amount")
