"""Run with:  uv run --with pytest --with pypdf pytest tests/"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import cart  # noqa: E402
import mapping  # noqa: E402
import reminders  # noqa: E402
import store  # noqa: E402


@pytest.fixture(autouse=True)
def tmp_home(tmp_path, monkeypatch):
    monkeypatch.setenv("RESTOCKR_HOME", str(tmp_path))
    store.save_products([
        {"canonical_id": "fizz", "generic_spec": "Fizzy drink, 1 L", "brand_policy": "exact",
         "preferred_brand": "Fizz", "last_price_eur": "1.10", "cheapest_price_eur": "0.90"},
        {"canonical_id": "oats", "generic_spec": "Rolled oats, 500 g", "brand_policy": "any",
         "preferred_brand": "", "last_price_eur": "0.99", "cheapest_price_eur": "0.89"},
    ])
    store.save_options([{"canonical_id": "fizz", "rank": "1", "description": "Fizz 1 L",
                         "brand": "Fizz", "size": "1 L", "quantity": "8", "notes": ""}])


def line(**kw):
    base = {"item": "fizz", "canonical_id": "fizz", "units": 8, "product_id": 111,
            "product_name": "Fizz 6x1 L", "pack_units": 6, "price_eur": 6.60, "in_stock": True}
    return {**base, **kw}


def test_packs_round_up_and_report_it():
    r = cart.plan([line()], 20)
    l = r["lines"][0]
    assert (l["packs"], l["units_in_cart"], l["line_total_eur"]) == (2, 12, "13.20")
    assert "ROUNDED_UP" in l["flags"]
    assert r["add_items"] == [{"productId": 111, "quantity": 2}]


def test_exact_multiple_is_not_flagged():
    l = cart.plan([line(units=12)], 20)["lines"][0]
    assert l["packs"] == 2 and "ROUNDED_UP" not in l["flags"]


def test_shop_limit_caps_quantity():
    l = cart.plan([line(units=30, max_available=3)], 20)["lines"][0]
    assert (l["packs"], l["units_in_cart"]) == (3, 18)
    assert "CAPPED_AT_3" in l["flags"]


def test_out_of_stock_is_left_out_of_the_cart():
    r = cart.plan([line(in_stock=False)], 20)
    assert r["add_items"] == [] and r["lines"][0]["flags"] == ["OUT_OF_STOCK"]


def test_minimum_order_and_totals():
    r = cart.plan([line(units=6), line(item="oats", canonical_id="oats", units=1, product_id=222,
                                      product_name="Oats 500 g", pack_units=1, price_eur=0.79)], 20)
    assert r["total_eur"] == "7.39"
    assert r["below_minimum"] and r["missing_to_minimum_eur"] == "12.61"


def test_price_flags_per_unit():
    # 6.60 / 6 = 1.10 per unit: above the REWE cheapest (0.90), not above last (no last yet)
    l = cart.plan([line(units=6)], 20)["lines"][0]
    assert l["unit_now_eur"] == "1.10" and "ABOVE_REWE_CHEAPEST" in l["flags"]
    mapping.main(["x", "set", "fizz", "--rank", "1", "--product-id", "111", "--name", "Fizz 6x1 L",
                  "--pack-units", "6", "--match", "direct", "--price", "5.99"])
    l = cart.plan([line(units=6)], 20)["lines"][0]
    assert "PRICIER_THAN_LAST" in l["flags"] and l["unit_last_eur"] == "1.00"


def test_mapping_show_set_remove(capsys):
    mapping.main(["x", "show", "fizz", "oats", "nope"])
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("UNMAPPED\tfizz\trank=1\tFizz 1 L\tqty=8")
    assert out[1].startswith("UNMAPPED\toats\trank=0\tRolled oats, 500 g")
    assert out[2] == "NO_PRODUCT\tnope"
    assert mapping.main(["x", "set", "fizz", "--rank", "1", "--product-id", "111", "--name", "Fizz 6x1 L",
                         "--pack-units", "6", "--match", "guess"]) == 1  # invalid match kind
    assert mapping.main(["x", "set", "fizz", "--rank", "1", "--product-id", "111", "--name", "Fizz 6x1 L",
                         "--pack-units", "6", "--match", "confirmed"]) == 0
    capsys.readouterr()
    mapping.main(["x", "show", "fizz"])
    assert "MAPPED\tfizz\trank=1\tFizz 1 L\tqty=8\t-> 111\tFizz 6x1 L\tpack_units=6\tmatch=confirmed" \
        in capsys.readouterr().out
    assert mapping.main(["x", "price", "111", "6.10"]) == 0
    assert store.load_mapping()[0]["last_price_eur"] == "6.10"
    mapping.main(["x", "remove", "fizz", "--rank", "1"])
    assert store.load_mapping() == []


def test_reminders_items_are_cleaned():
    raw = [{"name": "  milk  ", "notes": None}, {"name": "", "notes": "x"},
           {"name": "palitinho  de sopa", "notes": "the  usual"}]
    assert reminders.clean_items(raw) == [
        {"name": "milk", "notes": ""}, {"name": "palitinho de sopa", "notes": "the usual"}]
