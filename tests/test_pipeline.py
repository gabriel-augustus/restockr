"""Run with:  uv run --with pytest --with pypdf pytest tests/"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_products  # noqa: E402
import catalog  # noqa: E402
import import_rewe_ebons as rewe  # noqa: E402
import store  # noqa: E402

FAKE = (ROOT / "tests/fixtures/rewe_ebon_fake.txt").read_text()


@pytest.fixture(autouse=True)
def tmp_home(tmp_path, monkeypatch):
    monkeypatch.setenv("RESTOCKR_HOME", str(tmp_path))


def purchases(text):
    return [{
        "source": l["source"], "order_id": l["order_id"], "ordered_at": l["ordered_at"],
        "product_name": l["product_name"], "quantity": l["quantity"],
        "paid_cents": round((l["line_total_eur"] + l["discount_eur"]) * 100),
    } for l in rewe.parse_ebon_text(text) if l["kind"] == "product"]


def test_parses_all_line_types():
    lines = rewe.parse_ebon_text(FAKE)
    by_name = {l["product_name"]: l for l in lines}
    assert lines[0]["order_id"] == "0999-2025-03-01-1234"
    assert lines[0]["ordered_at"] == "2025-03-01T12:34:00"
    milk = by_name["H-MILCH 3,5%"]
    assert (milk["quantity"], milk["unit_price_eur"], milk["line_total_eur"]) == (2, 1.09, 2.18)
    assert by_name["BANANEN LOSE"]["weight_kg"] == 0.725
    assert by_name["PASTINAKE"]["weight_kg"] == 0.49
    assert by_name["AVOCADO"]["discount_eur"] == -0.75
    assert by_name["PFAND 0,25 EURO"]["kind"] == "deposit"
    assert by_name["LEERGUT EINWEG"]["kind"] == "deposit_return"
    assert by_name["LEERGUT EINWEG"]["quantity"] == 2


def test_total_mismatch_is_rejected():
    with pytest.raises(rewe.ParseError, match="SUMME"):
        rewe.parse_ebon_text(FAKE.replace("7,78", "9,99"))


def test_kg_price_must_add_up():
    with pytest.raises(rewe.ParseError, match="PASTINAKE"):
        rewe.parse_ebon_text(FAKE.replace("2,99 EUR/kg", "3,99 EUR/kg"))


def test_unknown_line_is_rejected():
    with pytest.raises(rewe.ParseError, match="unrecognised"):
        rewe.parse_ebon_text(FAKE.replace("APFELSCHORLE", "NO PRICE HERE\nAPFELSCHORLE"))


def test_last_and_cheapest_price_and_idempotent_reimport():
    first = purchases(FAKE)  # 2025-03-01, milk 1.09
    later = purchases(FAKE.replace("Bon-Nr.:1234", "Bon-Nr.:5678")
                      .replace("01.03.2025", "01.04.2025")
                      .replace("2,18 B", "2,58 B").replace("x    1,09", "x    1,29")
                      .replace("7,78", "8,18"))
    assert store.record_purchases(later + first) == (2, 0)
    assert store.record_purchases(first) == (0, 1)  # already counted
    milk = next(v for v in store.load_variants() if v["product_name"] == "H-MILCH 3,5%")
    assert (milk["times_bought"], milk["total_quantity"]) == ("2", "4")
    assert (milk["last_price_eur"], milk["cheapest_price_eur"]) == ("1.29", "1.09")
    avocado = next(v for v in store.load_variants() if v["product_name"] == "AVOCADO")
    assert avocado["cheapest_price_eur"] == "1.74"  # 2.49 - 0.75 discount


def test_products_keep_judgment_and_flag_ties():
    store.record_purchases(purchases(FAKE))
    vs = store.load_variants()
    for v in vs:
        v["canonical_id"] = {"H-MILCH 3,5%": "milk", "APFELSCHORLE": "schorle"}.get(v["product_name"], "skip")
    vs.append({**vs[0], "product_name": "MILCH 2", "canonical_id": "milk"})  # tie with H-MILCH
    for v in vs:
        if v["product_name"] == "MILCH 2":
            v.update(times_bought="1", total_quantity="2", last_price_eur="0.99", cheapest_price_eur="0.99")
    store.save_variants(vs)

    prods, warns = build_products.build_products(store.load_variants(), [])
    assert {p["status"] for p in prods} == {"needs_spec"}

    prev = [{"canonical_id": "milk", "generic_spec": "UHT milk 1 L 3.5%", "brand_policy": "exact"},
            {"canonical_id": "schorle", "generic_spec": "Apple spritzer 1 L", "brand_policy": "exact"},
            {"canonical_id": "salt", "generic_spec": "Salt 500 g", "brand_policy": "any"}]
    prods, warns = build_products.build_products(store.load_variants(), prev)
    by = {p["canonical_id"]: p for p in prods}
    assert by["milk"]["status"] == "tie"
    assert by["milk"]["cheapest_price_eur"] == "0.99"
    assert by["salt"]["status"] == "manual"

    prev[0]["brand_policy"] = "store_brand_or_cheapest"  # brand doesn't matter -> no tie
    prods, _ = build_products.build_products(store.load_variants(), prev)
    assert {p["canonical_id"]: p["status"] for p in prods}["milk"] == "ok"


def test_aliases(capsys):
    store.save_products([{"canonical_id": "milk", "generic_spec": "UHT milk 1 L",
                          "brand_policy": "any"}])
    assert catalog.main(["x", "alias", "  Milk ", "milk", "--quantity", "2"]) == 0
    assert catalog.main(["x", "alias", "Milch", "milk"]) == 0
    assert catalog.main(["x", "alias", "eggs", "nope"]) == 1
    capsys.readouterr()
    catalog.main(["x", "lookup", "MILK", "milch", "bread"])
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("KNOWN\tMILK\tmilk\tqty=2")
    assert out[1].startswith("KNOWN\tmilch\tmilk\tqty=1")
    assert out[2] == "UNKNOWN\tbread"
