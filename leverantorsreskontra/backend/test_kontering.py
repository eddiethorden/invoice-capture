"""Tester för konteringsmotorn (BAS + moms).

    backend/.venv/bin/python test_kontering.py

Validerar det som måste stämma: momsbeloppen, att verifikatet balanserar, och
att omvänd skattskyldighet bokas rätt (självdeklarerad moms nettar till noll).
"""

from decimal import Decimal

from app import bas, kontering
from app.kontering import Konteringsrad

D = Decimal


def _konto_belopp(ver, konto):
    """(debet, kredit) summerat för ett konto i verifikatet."""
    d = sum((r.debet for r in ver.rader if r.konto == konto), D("0"))
    k = sum((r.kredit for r in ver.rader if r.konto == konto), D("0"))
    return d, k


def test_inhemsk_25():
    ver = kontering.bygg_verifikat([Konteringsrad("6110", D("1000.00"), "SE25")])
    assert ver.balanserar
    assert _konto_belopp(ver, "6110") == (D("1000.00"), D("0"))
    assert _konto_belopp(ver, bas.INGAENDE_MOMS) == (D("250.00"), D("0"))
    assert _konto_belopp(ver, bas.LEVERANTORSSKULDER) == (D("0"), D("1250.00"))
    print("OK  inhemsk 25 %: 1000 netto -> 250 moms, skuld 1250, balanserar")


def test_satser_12_och_6():
    v12 = kontering.bygg_verifikat([Konteringsrad("5010", D("1000.00"), "SE12")])
    assert _konto_belopp(v12, bas.INGAENDE_MOMS)[0] == D("120.00")
    assert _konto_belopp(v12, bas.LEVERANTORSSKULDER)[1] == D("1120.00")
    v6 = kontering.bygg_verifikat([Konteringsrad("5010", D("1000.00"), "SE06")])
    assert _konto_belopp(v6, bas.INGAENDE_MOMS)[0] == D("60.00")
    print("OK  satser 12 % -> 120, 6 % -> 60")


def test_momsfritt():
    ver = kontering.bygg_verifikat([Konteringsrad("6570", D("500.00"), "SE00")])
    assert _konto_belopp(ver, bas.INGAENDE_MOMS) == (D("0"), D("0"))
    assert _konto_belopp(ver, bas.LEVERANTORSSKULDER) == (D("0"), D("500.00"))
    print("OK  momsfritt: ingen ingående moms, skuld = netto")


def test_omvand_skattskyldighet():
    # Bygg/EU-tjänst: leverantören fakturerar netto; köparen självdeklarerar moms.
    ver = kontering.bygg_verifikat([Konteringsrad("4415", D("1000.00"), "RC25")])
    assert ver.balanserar
    assert _konto_belopp(ver, "4415") == (D("1000.00"), D("0"))
    # beräknad ingående (debet) och utgående omvänd (kredit) — lika stora
    assert _konto_belopp(ver, bas.BERAKNAD_INGAENDE_MOMS_UTLAND) == (D("250.00"), D("0"))
    assert _konto_belopp(ver, bas.UTGAENDE_MOMS_OMVANT_25) == (D("0"), D("250.00"))
    # leverantörsskuld = endast netto (ingen moms betalas till leverantören)
    assert _konto_belopp(ver, bas.LEVERANTORSSKULDER) == (D("0"), D("1000.00"))
    print("OK  omvänd skattskyldighet: moms nettar till noll, skuld 1000, balanserar")


def test_blandade_rader():
    ver = kontering.bygg_verifikat([
        Konteringsrad("6110", D("800.00"), "SE25"),     # 200 moms
        Konteringsrad("5010", D("1000.00"), "SE12"),    # 120 moms
        Konteringsrad("4415", D("500.00"), "RC25"),     # omvänd, netto i skuld
    ], angivet_total=D("2920.00"))
    assert ver.balanserar
    # ingående moms 2640 = 200 + 120 (ej RC-raden)
    assert _konto_belopp(ver, bas.INGAENDE_MOMS)[0] == D("320.00")
    # skuld = 1000 + 1120 + 500
    assert _konto_belopp(ver, bas.LEVERANTORSSKULDER)[1] == D("2620.00")
    # angivet bruttototal 2920 -> differens 2620 - 2920 = -300 (RC-momsen ingår ej i skuld)
    assert ver.differens_mot_angivet_total == D("-300.00")
    print("OK  blandade rader: 2640=320, skuld=2620, balanserar")


def test_avrundning():
    # 333.33 * 25 % = 83.3325 -> 83.33 (öresavrundning), skuld 416.66, balanserar
    ver = kontering.bygg_verifikat([Konteringsrad("6110", D("333.33"), "SE25")])
    assert _konto_belopp(ver, bas.INGAENDE_MOMS)[0] == D("83.33")
    assert _konto_belopp(ver, bas.LEVERANTORSSKULDER)[1] == D("416.66")
    assert ver.balanserar
    print("OK  öresavrundning: 83.3325 -> 83.33, balanserar")


def test_fel_kontotyp():
    try:
        kontering.bygg_verifikat([Konteringsrad("2440", D("100.00"), "SE25")])
    except ValueError:
        print("OK  vägrar kontera mot icke-kostnadskonto (2440)")
        return
    raise AssertionError("borde ha vägrat kontera mot 2440")


if __name__ == "__main__":
    test_inhemsk_25()
    test_satser_12_och_6()
    test_momsfritt()
    test_omvand_skattskyldighet()
    test_blandade_rader()
    test_avrundning()
    test_fel_kontotyp()
    print("\nalla konteringstester godkända")
