"""Tester för SIE4-exporten.

    backend/.venv/bin/python test_sie.py

Validerar det som måste stämma: rätt SIE-poster i rätt ordning, teckenförsedda
belopp som summerar till 0 per verifikat, PC8-kodning (cp437), och att svenska
tecken överlever.
"""

from decimal import Decimal

from app import sie

# Två verifikat: inhemsk 25 % och omvänd skattskyldighet — som konteringsmotorn
# bygger dem (rader med konto/kontonamn/debet/kredit).
FAKTUROR = [
    {
        "supplier": "Åkerbergs Kontor AB", "invoice_number": "2026-4035",
        "invoice_date": "2026-07-10",
        "verifikat": {"rader": [
            {"konto": "6110", "kontonamn": "Kontorsmateriel", "debet": "800.00", "kredit": "0", "text": ""},
            {"konto": "2640", "kontonamn": "Ingående moms", "debet": "200.00", "kredit": "0", "text": ""},
            {"konto": "2440", "kontonamn": "Leverantörsskulder", "debet": "0", "kredit": "1000.00", "text": ""},
        ]},
    },
    {
        "supplier": "Bygg & Fräs AB", "invoice_number": "2026-4041",
        "invoice_date": "10.07.2026",
        "verifikat": {"rader": [
            {"konto": "4415", "kontonamn": "Inköpta tjänster omvänd", "debet": "500.00", "kredit": "0", "text": ""},
            {"konto": "2645", "kontonamn": "Beräknad ingående moms", "debet": "125.00", "kredit": "0", "text": ""},
            {"konto": "2614", "kontonamn": "Utgående moms omvänd", "debet": "0", "kredit": "125.00", "text": ""},
            {"konto": "2440", "kontonamn": "Leverantörsskulder", "debet": "0", "kredit": "500.00", "text": ""},
        ]},
    },
]


def _trans_sum(block: list[str]) -> Decimal:
    tot = Decimal("0")
    for line in block:
        if line.strip().startswith("#TRANS"):
            tot += Decimal(line.split("{}")[1].strip().split()[0])
    return tot


def test_poster_och_ordning():
    txt = sie.bygg_sie(FAKTUROR, fnamn="KASE AB", orgnr="556000-0000",
                       sign="ET", gen_datum="20260726", serie="A")
    for post in ("#FLAGGA 0", "#FORMAT PC8", "#SIETYP 4",
                 "#GEN 20260726", '#FNAMN "KASE AB"', "#ORGNR 556000-0000"):
        assert post in txt, f"saknar {post}"
    assert '#KONTO 2440 "Leverantörsskulder"' in txt
    assert "#KTYP 2440 S" in txt and "#KTYP 6110 K" in txt
    assert txt.index("#KONTO") < txt.index("#VER")  # kontoplan före verifikat
    print("OK  rätt poster i rätt ordning (kontoplan före verifikationer)")


def test_verifikat_balanserar():
    txt = sie.bygg_sie(FAKTUROR, fnamn="KASE AB", orgnr="556000-0000", sign="ET")
    lines = txt.splitlines()
    # Dela upp i #VER-block och kontrollera att varje summerar till 0.
    blocks, cur, inside = [], [], False
    for ln in lines:
        if ln == "{":
            inside, cur = True, []
        elif ln == "}":
            inside = False
            blocks.append(cur)
        elif inside:
            cur.append(ln)
    assert len(blocks) == 2
    for b in blocks:
        assert _trans_sum(b) == Decimal("0"), "verifikatet summerar inte till 0"
    print("OK  varje #VER summerar till 0 (teckenförsedda belopp)")


def test_tecken_och_datum():
    txt = sie.bygg_sie(FAKTUROR, fnamn="KASE AB", orgnr="556000-0000", sign="ET")
    assert "#VER A 1 20260710" in txt          # ISO-datum
    assert "#VER A 2 20260710" in txt          # dd.mm.yyyy -> YYYYMMDD
    assert "Åkerbergs Kontor AB 2026-4035" in txt
    # PC8/cp437: svenska tecken ska gå att koda och avkoda tillbaka.
    data = sie.till_bytes(txt)
    assert isinstance(data, bytes)
    assert "Åkerbergs" in data.decode("cp437")
    print("OK  datum normaliseras, svenska tecken överlever cp437")


def test_belopp_tecken():
    # Debet positivt, kredit negativt.
    assert sie._belopp("800.00", "0") == "800.00"
    assert sie._belopp("0", "1000.00") == "-1000.00"
    print("OK  belopp: debet positivt, kredit negativt")


if __name__ == "__main__":
    test_poster_och_ordning()
    test_verifikat_balanserar()
    test_tecken_och_datum()
    test_belopp_tecken()
    print("\nalla SIE-tester godkända")
