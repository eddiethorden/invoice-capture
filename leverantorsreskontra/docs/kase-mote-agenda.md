# KASE — mötesagenda: Leverantörsreskontra

**Syfte:** besluta de öppna punkterna så att leverantörsreskontran kan anpassas
mot KASE:s kontoplan, moms, dimensioner, bank och driftmiljö och produktionssättas.

| | |
|---|---|
| **Längd** | ~90 min |
| **Deltagare** | KASE: ekonomi-/redovisningsansvarig, IT/systemägare · Republic Consulting: utvecklare |
| **Förberedelse (pre-read)** | [`systemoversikt.html`](systemoversikt.html) · [`kase-avstamningspunkter.md`](kase-avstamningspunkter.md) |
| **KASE tar med** | Kontoplan (BAS), momsinställningar, register för kostnadsställe & projekt, bankuppgifter + betalformat, gällande attestregler, uppgift om e-fakturaväg (Peppol) |

Detaljerna för varje punkt finns i [avstämningspunkterna](kase-avstamningspunkter.md);
agendan nedan grupperar dem i beslutsbara block.

---

## 1. Intro & demo — 10 min
Genomgång av kärnflödet: inläsning → granskning → kontering → attest → SIE4 + pain.001.
- **Mål:** gemensam bild av vad som redan fungerar end-to-end.

## 2. Kontering & moms — 20 min · *avstämningspunkt 1–3*
- **Beslut som behövs:**
  - Kontoplan: kostnadskonton, 2440, 2640/2645, 2614 — mot KASE:s BAS.
  - Momskoder utöver 25/12/6 %, momsfritt och omvänd skattskyldighet; konton för utgående moms.
  - Register för kostnadsställe (SIE-dim 1) och projekt (dim 6) — koder + namn. Fler dimensioner?
- **Underlag:** KASE:s kontoplan, momsinställningar, dimensionsregister.

## 3. Utdata: bokföring & betalning — 20 min · *avstämningspunkt 4–5*
- **Beslut som behövs:**
  - SIE4: verifikationsserie, företagsuppgifter (`#FNAMN`/`#ORGNR`), målsystem för import.
  - pain.001: vilken **bank** och därmed profil (`.001.03` / `.001.09` / Bankgirot-variant), debtor-konto, `CdtrAgt`-krav för BG/PG.
- **Underlag:** bankuppgifter, önskat betalformat, redovisningssystem.

## 4. Attest & behörigheter — 15 min · *avstämningspunkt 6–7*
- **Beslut som behövs:**
  - Beloppsgränser per attestant/roll, attesthierarki och eskalering.
  - Behörigheter → kräver användar-/rollmodell + inloggning.
  - Leverantörsmatchning (orgnr/VAT) och om nya leverantörer skapas automatiskt.
- **Underlag:** gällande attestregler och roller.

## 5. Omfattning & drift — 15 min · *avstämningspunkt 8–11*
- **Beslut som behövs:**
  - E-faktura in via Peppol BIS 3.0 / Svefaktura — prioritet och accesspunkt.
  - Arkivering enligt Bokföringslagen (7 år) — var och hur.
  - Produktionsstack: PostgreSQL/objektlagring, autentisering, containerisering, hosting.
  - Claude vision: API-kredit, modellval (Opus vs Sonnet), mock- vs live-läge.
- **Underlag:** IT-/driftförutsättningar hos KASE.

## 6. Beslut, ansvar & nästa steg — 10 min
Summera beslut, sätt ägare och deadline, prioritera roadmap.

---

## Beslutslogg *(fylls i under mötet)*

| # | Punkt | Beslut | Ägare | Deadline |
|---|---|---|---|---|
| 1 | Kontoplan (BAS) | | | |
| 2 | Momskoder & momskonton | | | |
| 3 | Dimensioner (KS / projekt) | | | |
| 4 | SIE4 (serie, målsystem) | | | |
| 5 | Bank & pain.001-profil | | | |
| 6 | Attestregler & roller | | | |
| 7 | Leverantörsregister | | | |
| 8 | E-faktura in (Peppol) | | | |
| 9 | Arkivering | | | |
| 10 | Produktionsstack | | | |
| 11 | Claude vision (kredit/modell) | | | |

## Åtgärder

- [ ]
- [ ]
- [ ]
