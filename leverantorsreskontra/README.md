# Leverantörsreskontra

En fristående leverantörsreskontra byggd enligt svensk standard — läser in
leverantörsfakturor, låter en människa granska och attestera, konterar mot
BAS-kontoplanen med korrekt momshantering, och lämnar ut betal- och bokförings-
underlag (bankgiro/OCR, SIE, pain.001).

> A standalone Swedish accounts-payable subledger (*leverantörsreskontra*).
> Seeded from the KASE invoice-capture demo (tag `kase-demo`); this branch
> reworks it toward Swedish accounting standards as its own app.

## Härkomst / provenance

Kopierad från demots `backend/` och `frontend/`. Det som återanvänds direkt:

- **Inläsning + granskningsvy** — fakturan till vänster, avlästa värden som
  färgkodade rutor till höger, tangentbordsflöde. (`frontend/`, extraction)
- **Oföränderligt verifikat / audit trail** — hash-kedjad, append-only. Passar
  **Bokföringslagens** krav på oföränderlighet och 7 års arkivering.
- **Struktur-validering** — orgnr, VAT-nr, IBAN, **OCR-referens (Luhn)** finns
  redan (python-stdnum).
- **Transaktionell outbox** — säker, idempotent utlämning.
- **Reskontra-modul** — `ap_module.py` som grund för själva reskontran.

## Att bygga — svensk standard

Prioritetsordning bekräftas med KASE.

1. **BAS-kontoplan** — kontera kostnad mot BAS (t.ex. 4000/5000-serien),
   leverantörsskuld **2440**, ingående moms **2640/2641**.
2. **Moms** — 25/12/6 %, **omvänd skattskyldighet** (bygg + EU-förvärv),
   EU-moms. Momsrapportunderlag.
3. **Betalning** — **bankgiro/plusgiro** + **OCR**, samt **ISO 20022 pain.001**
   betalfil till bank. Betalningsförslag och förfallobevakning.
4. **E-faktura in** — **Peppol BIS Billing 3.0 / Svefaktura**, inte bara
   PDF-scanning.
5. **Attestflöde** — granskare → attestant, med behörigheter och attestregler.
6. **SIE4** — export/import mot Fortnox/Visma m.fl.
7. **Arkivering** — 7 år, oföränderliga verifikat (Bokföringslagen).

## Milstolpe 1

_Bestäms med KASE:_ **BAS + moms-kontering** eller **SIE4/bankgiro-utdata**.

## Köra

Samma som demot (tills strukturen byggs om):

```bash
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000
# frontend
cd ../frontend && npm install && npm run dev
```

## Namn

Mappen/grenen heter `leverantorsreskontra` (ASCII, utan mellanslag) av
verktygsskäl; visningsnamnet är **Leverantörsreskontra**.
