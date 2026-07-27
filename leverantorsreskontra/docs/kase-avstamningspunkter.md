# Avstämningspunkter med KASE

Öppna beslut som behöver bekräftas med KASE innan leverantörsreskontran är
produktionsklar. För varje punkt anges **vad som behöver bekräftas**, det
**nuvarande antagandet** i koden, och **var** det ligger.

Kärnflödet (inläsning → granskning → kontering → attest → SIE4 + pain.001)
fungerar end-to-end; punkterna nedan gäller att anpassa det mot KASE:s verkliga
kontoplan, bank, register och driftmiljö.

## 1. Kontoplan (BAS)

- **Att bekräfta:** kontonumren mot KASE:s faktiska kontoplan — kostnadskonton,
  leverantörsskuld (2440), ingående moms (2640/2645) och utgående moms omvänd
  skattskyldighet (2614). Behövs konteringsmallar per leverantör?
- **Antagande i dag:** standard-BAS 2025-urval.
- **Var:** `backend/app/bas.py`

## 2. Moms

- **Att bekräfta:** vilka momskoder som behövs utöver 25/12/6 %, momsfritt och
  omvänd skattskyldighet (RC 25 %). T.ex. EU-förvärv av varor separat, och rätt
  konton för beräknad utgående moms (2614 vs 2615/2616/2617).
- **Antagande i dag:** `SE25/SE12/SE06/SE00` + `RC25`.
- **Var:** `backend/app/moms.py`, `backend/app/kontering.py`

## 3. Dimensioner

- **Att bekräfta:** KASE:s faktiska register för kostnadsställe (SIE-dim 1) och
  projekt (SIE-dim 6) — koder och namn. Behövs fler dimensioner?
- **Antagande i dag:** exempellistor.
- **Var:** `backend/app/dimensioner.py`

## 4. SIE4-export

- **Att bekräfta:** verifikationsserie (`#VER`-serie), företagsuppgifter
  (`#FNAMN`/`#ORGNR`) och målsystem för import (Fortnox/Visma/annat).
- **Antagande i dag:** serie `A`; företagsuppgifter via env
  `SIE_FNAMN/SIE_ORGNR/SIE_SIGN/SIE_SERIE`.
- **Var:** `backend/app/sie.py`

## 5. Betalfil (pain.001)

- **Att bekräfta:** vilken **bank** och därmed profil — generisk
  `pain.001.001.03`, en nyare `.001.09`, eller en Bankgirot-specifik variant.
  Debtor-konto (IBAN/BIC). Om banken kräver `CdtrAgt` för bankgiro/plusgiro.
- **Antagande i dag:** `pain.001.001.03`, IBAN/BG/PG som mottagarkonto, debtor
  via env `PAIN_DBTR_NM/IBAN/BIC`; `CdtrAgt` utelämnad för BG/PG.
- **Var:** `backend/app/pain.py`

## 6. Attestflöde

- **Att bekräfta:** beloppsgränser per attestant/roll, attesthierarki och
  eskalering över gräns, samt behörigheter (vem får granska/attestera). Kräver
  en användar- och rollmodell samt autentisering.
- **Antagande i dag:** enkel global beloppsgräns (`ATTEST_BELOPPSGRANS`), fyra
  ögon på namn (ingen inloggning).
- **Var:** `backend/app/store.py`, `backend/app/main.py`

## 7. Leverantörsregister

- **Att bekräfta:** hur leverantör matchas (orgnr/VAT-nr) och om nya ska kunna
  skapas automatiskt. Fortnox-adaptern kräver ett befintligt `SupplierNumber`.
- **Var:** `backend/app/fortnox.py`

## 8. E-faktura in (Peppol / Svefaktura)

- **Att bekräfta:** om inläsning ska ske via **Peppol BIS 3.0 / Svefaktura**
  utöver PDF-scanning, och i så fall via vilken accesspunkt.
- **Status:** ej byggt (endast PDF-inläsning i dag).

## 9. Arkivering

- **Att bekräfta:** lagringskrav enligt Bokföringslagen (7 år) — var och hur
  verifikat/underlag arkiveras. Den hash-kedjade, oföränderliga loggen finns på
  plats som grund.
- **Var:** `backend/app/store.py`, `backend/app/db.py`

## 10. Driftmiljö

- **Att bekräfta:** produktionsstack — PostgreSQL/objektlagring i stället för
  SQLite, autentisering, containerisering och drift/hosting.
- **Status:** kör i dag lokalt på SQLite; ingen auth eller containerisering.

## 11. Claude vision (avläsning)

- **Att bekräfta:** API-kredit och modellval (Opus vs Sonnet för kostnad per
  sida), samt mock- vs live-läge i olika miljöer.
- **Antagande i dag:** live om kredential finns, annars mock
  (`INVOICE_CAPTURE_MOCK=1` tvingar mock).
- **Var:** `backend/app/extraction.py`
