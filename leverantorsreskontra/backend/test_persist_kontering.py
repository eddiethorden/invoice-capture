"""Test: konteringen (konto + momskod) persisteras och verifikatet byggs & lagras.

    INVOICE_DB_PATH=/tmp/persist_test.db backend/.venv/bin/python test_persist_kontering.py
"""

import os

os.environ["INVOICE_DB_PATH"] = "/tmp/persist_test.db"
for _p in ("/tmp/persist_test.db", "/tmp/persist_test.db-wal", "/tmp/persist_test.db-shm"):
    try:
        os.remove(_p)
    except FileNotFoundError:
        pass

from app import db, store  # noqa: E402

db.init()


def _field(key, value, label=""):
    return {"key": key, "label": label or key, "value": value, "confidence": 0.99,
            "found": True, "page": 1, "status": "green", "box": None}


def _line(index, description, amount):
    return {"index": index, "description": description, "quantity": "1",
            "unit_price": amount, "amount": amount, "confidence": 0.98,
            "page": 1, "status": "green", "box": None}


RESULT = {
    "id": "test-inv-1",
    "filename": "leverantorsfaktura.pdf",
    "pages": [{"width": 1000, "height": 1400}],
    "checks": {},
    "signals": [],
    "fields": [
        _field("supplier_name", "Bygg & Data AB"),
        _field("total_amount", "1300,00"),
        _field("currency", "SEK"),
    ],
    "line_items": [
        _line(0, "Kontorsmateriel", "800,00"),
        _line(1, "Byggtjänst (omvänd moms)", "500,00"),
    ],
}


def main():
    store.save_invoice(RESULT)

    # Innan kontering: inget verifikat, tom kontering.
    r0 = store.get_result("test-inv-1")
    assert r0["verifikat"] is None
    assert all(li["konto"] == "" and li["momskod"] == "" for li in r0["line_items"])
    print("OK  före verifiering: ingen kontering, inget verifikat")

    # Verifiera med kontering: rad 0 = 6110/SE25, rad 1 = 4415/RC25.
    store.verify_invoice(
        "test-inv-1", field_values={}, projects={}, actor="anna",
        codings={0: {"konto": "6110", "momskod": "SE25"},
                 1: {"konto": "4415", "momskod": "RC25"}})

    r = store.get_result("test-inv-1")
    li = {x["index"]: x for x in r["line_items"]}
    assert li[0]["konto"] == "6110" and li[0]["momskod"] == "SE25"
    assert li[1]["konto"] == "4415" and li[1]["momskod"] == "RC25"
    print("OK  konto + momskod persisterade per rad")

    ver = r["verifikat"]
    assert ver is not None and ver["balanserar"] is True
    # 6110 debet 800; 2640 debet 200 (25% på 800); RC: 2645 debet 125, 2614 kredit 125
    konton = {row["konto"] for row in ver["rader"]}
    assert {"6110", "2640", "4415", "2645", "2614", "2440"} <= konton
    # leverantörsskuld 2440 = 800 + 200 (moms) + 500 (RC netto) = 1500
    skuld = next(row for row in ver["rader"] if row["konto"] == "2440")
    assert skuld["kredit"] == "1500.00"
    assert ver["summa_debet"] == ver["summa_kredit"]
    print(f"OK  verifikat byggt & lagrat: balanserar, skuld 2440 = {skuld['kredit']}")

    # Konteringen syns i handover-payloaden.
    with db.connect() as c:
        payload = store._handover_payload(c, "test-inv-1")
    assert payload["allocation_lines"][0]["konto"] == "6110"
    assert payload["allocation_lines"][1]["momskod"] == "RC25"
    print("OK  handover-payload innehåller konto + momskod")

    # Audit: kontering + verifikat loggade.
    actions = [a["action"] for a in store.get_audit("test-inv-1")]
    assert "kontering_satt" in actions and "verifikat_byggt" in actions
    print("OK  audit: kontering_satt + verifikat_byggt loggade")

    print("\nalla persist-tester godkända")


if __name__ == "__main__":
    main()
