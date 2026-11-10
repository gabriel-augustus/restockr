# /// script
# requires-python = ">=3.10"
# ///
"""Cart arithmetic for a shopping run. Claude does the judgment; this does the maths.

Usage:
  uv run cart.py plan [--min-order 20] < lines.json

lines.json: a JSON list, one object per list item, with live shop data filled in:
  {"item": "wasser", "canonical_id": "sparkling-water", "units": 12,
   "product_id": 900103, "product_name": "Sparkling water 6x0.75 l", "pack_units": 6,
   "price_eur": 5.99, "in_stock": true, "max_available": 3}
  units:         how many the user wants, in their own units (bottles, packs, pieces)
  pack_units:    how many of those units one shop product holds (default 1)
  max_available: the shop's per-order limit for this product (optional)

Prints a report and, last, one line starting with ADD_ITEMS followed by the JSON for
the shop's add-to-cart call. Prices compare per unit:
  now       shop price / pack_units
  last      last price seen at this shop (mapping.csv), per unit
  rewe_last / rewe_cheapest   from products.csv (receipts), per unit; sizes may differ
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import store  # noqa: E402


def _c(eur) -> int | None:
    return None if eur in (None, "") else round(float(eur) * 100)


def _e(c: int | None) -> str:
    return "-" if c is None else f"{c / 100:.2f}"


def plan(lines: list[dict], min_order_eur: float, shop: str = "knuspr") -> dict:
    products = {p["canonical_id"]: p for p in store.load_products()}
    last_seen = {m["product_id"]: m["last_price_eur"] for m in store.load_mapping() if m["shop"] == shop}
    out, add, total_c = [], [], 0
    for l in lines:
        units = int(l["units"])
        pack = int(l.get("pack_units") or 1)
        r = {"item": l["item"], "product_name": l.get("product_name", ""), "units_wanted": units,
             "flags": []}
        if not l.get("in_stock", True):
            r.update(packs=0, units_in_cart=0, line_total_eur="0.00")
            r["flags"].append("OUT_OF_STOCK")
            out.append(r)
            continue
        packs = -(-units // pack)  # round up: never fewer than asked for
        limit = l.get("max_available")
        if limit is not None and packs > int(limit):
            packs = int(limit)
            r["flags"].append(f"CAPPED_AT_{limit}")
        if packs * pack > units:
            r["flags"].append("ROUNDED_UP")
        price_c = _c(l["price_eur"])
        line_c = price_c * packs
        total_c += line_c
        p = products.get(l.get("canonical_id"), {})
        last_c = _c(last_seen.get(str(l["product_id"])))
        now_unit = price_c / pack
        r.update(
            product_id=l["product_id"], packs=packs, units_in_cart=packs * pack,
            line_total_eur=_e(line_c),
            unit_now_eur=_e(round(now_unit)),
            unit_last_eur=_e(None if last_c is None else round(last_c / pack)),
            unit_rewe_last_eur=p.get("last_price_eur") or "-",
            unit_rewe_cheapest_eur=p.get("cheapest_price_eur") or "-",
        )
        if last_c is not None and price_c > last_c:
            r["flags"].append("PRICIER_THAN_LAST")
        cheapest_c = _c(p.get("cheapest_price_eur"))
        if cheapest_c is not None and now_unit > cheapest_c:
            r["flags"].append("ABOVE_REWE_CHEAPEST")
        out.append(r)
        add.append({"productId": int(l["product_id"]), "quantity": packs})
    min_c = round(min_order_eur * 100)
    return {"lines": out, "total_eur": _e(total_c), "min_order_eur": _e(min_c),
            "below_minimum": total_c < min_c, "missing_to_minimum_eur": _e(max(0, min_c - total_c)),
            "add_items": add}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("plan"); s.add_argument("--min-order", type=float, default=20.0)
    a = ap.parse_args(argv[1:])
    result = plan(json.load(sys.stdin), a.min_order)
    print("item\tproduct\twanted\tpacks\tin_cart\tline\tunit_now\tunit_last\trewe_last\trewe_cheapest\tflags")
    for r in result["lines"]:
        print("\t".join(str(x) for x in (
            r["item"], r["product_name"], r["units_wanted"], r.get("packs", 0), r.get("units_in_cart", 0),
            r["line_total_eur"], r.get("unit_now_eur", "-"), r.get("unit_last_eur", "-"),
            r.get("unit_rewe_last_eur", "-"), r.get("unit_rewe_cheapest_eur", "-"),
            ",".join(r["flags"]) or "-")))
    print(f"TOTAL\t{result['total_eur']}\tmin_order\t{result['min_order_eur']}"
          + (f"\tBELOW_MINIMUM by {result['missing_to_minimum_eur']}" if result["below_minimum"] else ""))
    print("ADD_ITEMS " + json.dumps(result["add_items"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
