"""SIE4-export — svensk standard för bokföringsutbyte (SIE typ 4).

Builds a SIE type-4 file of supplier-invoice vouchers (verifikationer) from the
stored verifikat, importable into Fortnox/Visma and other Swedish systems.

Format notes (SIE-standarden):
  * Teckenuppsättning är **PC8 (Code Page 437)** — deklareras med #FORMAT PC8
    och filen ska kodas som cp437 (görs i API-lagret).
  * Belopp i #TRANS är teckenförsedda: debet positivt, kredit negativt, och
    summan inom ett #VER ska bli 0 (verifikatet balanserar).
  * En rad per post, poster inleds med #. Strängar med mellanslag citeras.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from . import dimensioner

PROGRAM = "Leverantorsreskontra"
VERSION = "1.0"


def _sie_datum(raw: str | None, fallback: str) -> str:
    """Tolka ett datum till YYYYMMDD; annars fallback."""
    if raw:
        raw = raw.strip()
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%Y%m%d"):
            try:
                return datetime.strptime(raw, fmt).strftime("%Y%m%d")
            except ValueError:
                continue
    return fallback


def _ktyp(konto: str) -> str | None:
    """SIE-kontotyp från BAS-klass (kontots första siffra): T/S/I annars K."""
    return {"1": "T", "2": "S", "3": "I"}.get(konto[:1], "K") if konto else None


def _belopp(debet: str, kredit: str) -> str:
    """Teckenförsett SIE-belopp: debet positivt, kredit negativt."""
    v = Decimal(debet or "0") - Decimal(kredit or "0")
    return f"{v:.2f}"


def _cit(s: str) -> str:
    """SIE-sträng inom citattecken; escape:a bakåtstreck och citattecken."""
    return '"' + (s or "").replace("\\", "\\\\").replace('"', '\\"') + '"'


def bygg_sie(fakturor: list[dict], *, fnamn: str, orgnr: str, sign: str,
             gen_datum: str | None = None, serie: str = "A") -> str:
    """Bygg SIE4-texten.

    fakturor: lista av {supplier, invoice_number, invoice_date, verifikat}, där
    verifikat är den lagrade dicten (rader med konto/kontonamn/debet/kredit).
    gen_datum: YYYYMMDD (default: idag).
    """
    gen_datum = gen_datum or date.today().strftime("%Y%m%d")
    rader: list[str] = []
    add = rader.append

    add("#FLAGGA 0")
    add(f"#PROGRAM {_cit(PROGRAM)} {VERSION}")
    add("#FORMAT PC8")
    add(f"#GEN {gen_datum} {_cit(sign)}")
    add("#SIETYP 4")
    add(f"#FNAMN {_cit(fnamn)}")
    add(f"#ORGNR {orgnr}")

    # Kontoplan: alla konton som förekommer i verifikaten.
    konton: dict[str, str] = {}
    for f in fakturor:
        for r in f["verifikat"]["rader"]:
            konton.setdefault(r["konto"], r["kontonamn"])
    for nr in sorted(konton):
        add(f"#KONTO {nr} {_cit(konton[nr])}")
        kt = _ktyp(nr)
        if kt:
            add(f"#KTYP {nr} {kt}")

    # Dimension 1: kostnadsställe — deklarera dimensionen och de objekt som används.
    ks_koder = sorted({r.get("kostnadsstalle") for f in fakturor
                       for r in f["verifikat"]["rader"] if r.get("kostnadsstalle")})
    dim = dimensioner.SIE_DIM_KOSTNADSSTALLE
    if ks_koder:
        add(f'#DIM {dim} "Kostnadsställe"')
        for kod in ks_koder:
            add(f'#OBJEKT {dim} "{kod}" {_cit(dimensioner.namn(kod))}')

    # En verifikation per faktura.
    for i, f in enumerate(fakturor, start=1):
        datum = _sie_datum(f.get("invoice_date"), gen_datum)
        text = " ".join(x for x in (f.get("supplier"), f.get("invoice_number")) if x)
        add(f"#VER {serie} {i} {datum} {_cit(text)}")
        add("{")
        for r in f["verifikat"]["rader"]:
            ks = r.get("kostnadsstalle")
            objekt = f'{{{dim} "{ks}"}}' if ks else "{}"
            add(f"   #TRANS {r['konto']} {objekt} {_belopp(r['debet'], r['kredit'])}")
        add("}")

    return "\n".join(rader) + "\n"


def till_bytes(text: str) -> bytes:
    """Koda SIE-texten som PC8 (cp437), som standarden kräver."""
    return text.encode("cp437", errors="replace")
