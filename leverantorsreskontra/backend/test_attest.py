"""Tester för attestflödet: granskning -> attest, fyra-ögon, beloppsgräns,
och att bara attesterade fakturor kan exporteras/betalas.

    INVOICE_DB_PATH=/tmp/attest_test.db backend/.venv/bin/python test_attest.py
"""

import os
from decimal import Decimal

os.environ["INVOICE_DB_PATH"] = "/tmp/attest_test.db"
for _p in ("/tmp/attest_test.db", "/tmp/attest_test.db-wal", "/tmp/attest_test.db-shm"):
    try:
        os.remove(_p)
    except FileNotFoundError:
        pass

from app import db, store  # noqa: E402

db.init()


def _f(k, v):
    return {"key": k, "label": k, "value": v, "confidence": 0.9,
            "found": True, "page": 1, "status": "green", "box": None}


def _li(i, d, a):
    return {"index": i, "description": d, "quantity": "1", "unit_price": a,
            "amount": a, "confidence": 0.9, "page": 1, "status": "green", "box": None}


def _ny(id_, belopp_rad="800,00"):
    store.save_invoice({
        "id": id_, "filename": "lev.pdf",
        "pages": [{"page": 1, "width": 1000, "height": 1400, "image_url": "/x"}],
        "checks": {"arithmetic_ok": True, "message": "ok"}, "signals": [],
        "fields": [_f("supplier_name", "Leverantör AB"), _f("total_amount", "1000,00"),
                   _f("currency", "SEK"), _f("iban", "SE1212341234123412341234")],
        "line_items": [_li(0, "Vara", belopp_rad)],
    })


def test_granskning_satts_vid_verify():
    _ny("a1")
    r = store.get_result("a1")
    assert r["attest_status"] == "utkast"
    store.verify_invoice("a1", {}, {}, actor="anna",
                         codings={0: {"konto": "6110", "momskod": "SE25"}})
    r = store.get_result("a1")
    assert r["attest_status"] == "granskad" and r["granskare"] == "anna"
    print("OK  verify (granskaren kodar) -> status granskad, granskare satt")


def test_fyra_ogon():
    try:
        store.attestera("a1", attestant="anna", actor="anna")  # samma som granskare
    except store.AttestError as e:
        assert "fyra ögon" in str(e)
        print("OK  fyra-ögon: samma person kan inte attestera sin egen granskning")
        return
    raise AssertionError("borde ha vägrat")


def test_beloppsgrans():
    try:
        store.attestera("a1", attestant="bertil", actor="bertil",
                        beloppsgrans=Decimal("500"))  # skuld 1000 > 500
    except store.AttestError as e:
        assert "beloppsgräns" in str(e)
        print("OK  beloppsgräns: attest vägras när skulden överstiger gränsen")
        return
    raise AssertionError("borde ha vägrat")


def test_attest_och_export_gate():
    # Före attest: inget att exportera/betala.
    assert store.verifikat_for_export() == []
    assert store.betalunderlag() == []
    # Attestera av annan person, inom gräns.
    store.attestera("a1", attestant="bertil", actor="bertil", beloppsgrans=Decimal("50000"))
    r = store.get_result("a1")
    assert r["attest_status"] == "attesterad" and r["attestant"] == "bertil"
    # Nu finns den för export och betalning.
    assert [f["id"] for f in store.verifikat_for_export()] == ["a1"]
    assert [b["id"] for b in store.betalunderlag()] == ["a1"]
    print("OK  export/betalning gatas på attest; attesterad faktura kommer med")


def test_omkontering_kraver_ny_attest():
    # Ny granskning (omkontering) nollställer attesten.
    store.verify_invoice("a1", {}, {}, actor="anna",
                         codings={0: {"konto": "5010", "momskod": "SE25"}})
    r = store.get_result("a1")
    assert r["attest_status"] == "granskad" and r["attestant"] is None
    assert store.verifikat_for_export() == []  # inte längre attesterad
    print("OK  omkontering nollställer attesten (måste attesteras på nytt)")


def test_avvisa():
    _ny("a2")
    store.verify_invoice("a2", {}, {}, actor="anna",
                         codings={0: {"konto": "6110", "momskod": "SE25"}})
    store.avvisa("a2", actor="bertil", kommentar="fel konto")
    r = store.get_result("a2")
    assert r["attest_status"] == "avvisad" and r["attest_kommentar"] == "fel konto"
    print("OK  avvisa: status avvisad med kommentar")


if __name__ == "__main__":
    test_granskning_satts_vid_verify()
    test_fyra_ogon()
    test_beloppsgrans()
    test_attest_och_export_gate()
    test_omkontering_kraver_ny_attest()
    test_avvisa()
    print("\nalla attest-tester godkända")
