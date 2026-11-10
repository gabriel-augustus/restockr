# /// script
# requires-python = ">=3.10"
# ///
"""Products -> shop products, built up one shopping list at a time.

Usage:
  uv run mapping.py show <canonical_id> ... [--shop knuspr]
      For each product: its options (rank order) and the shop product mapped to each,
      or UNMAPPED. Rank 0 = the product in general (used when it has no options).

  uv run mapping.py set <canonical_id> --rank N --product-id ID --name TEXT
          --pack-units N --match direct|confirmed [--price EUR] [--shop knuspr]
      Save or replace the mapping for one option (or rank 0).
      pack-units: how many of the user's units one shop product holds
      (a 6 x 1.25 L pack fulfils 6 bottles -> 6). Default 1.

  uv run mapping.py remove <canonical_id> --rank N [--shop knuspr]

  uv run mapping.py price <product_id> <EUR> [--shop knuspr]
      Record the price seen in the cart (becomes "last time" for the next run).
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import store  # noqa: E402


def show(ids: list[str], shop: str) -> int:
    products = {p["canonical_id"]: p for p in store.load_products()}
    mapping = [m for m in store.load_mapping() if m["shop"] == shop]
    options = store.load_options()
    for cid in ids:
        p = products.get(cid)
        if not p:
            print(f"NO_PRODUCT\t{cid}")
            continue
        opts = sorted((o for o in options if o["canonical_id"] == cid), key=lambda o: int(o["rank"]))
        targets = [(int(o["rank"]), o["description"], o["quantity"]) for o in opts] or \
                  [(0, p["generic_spec"], "")]
        for rank, desc, qty in targets:
            m = next((m for m in mapping if m["canonical_id"] == cid and int(m["rank"]) == rank), None)
            head = f"{cid}\trank={rank}\t{desc}" + (f"\tqty={qty}" if qty else "")
            if m:
                print(f"MAPPED\t{head}\t-> {m['product_id']}\t{m['product_name']}"
                      f"\tpack_units={m['pack_units']}\tmatch={m['match']}"
                      f"\tlast_price={m['last_price_eur'] or '-'}")
            else:
                print(f"UNMAPPED\t{head}\tpolicy={p['brand_policy']}"
                      + (f"\tbrand={p['preferred_brand']}" if p["preferred_brand"] else ""))
    return 0


def set_mapping(a: argparse.Namespace) -> int:
    if a.canonical_id not in {p["canonical_id"] for p in store.load_products()}:
        print(f"No product {a.canonical_id!r}")
        return 1
    if a.match not in store.MATCH_KINDS:
        print(f"--match must be one of {store.MATCH_KINDS}")
        return 1
    if a.pack_units < 1:
        print("--pack-units must be >= 1")
        return 1
    rows = [m for m in store.load_mapping()
            if not (m["shop"] == a.shop and m["canonical_id"] == a.canonical_id and int(m["rank"]) == a.rank)]
    rows.append({"shop": a.shop, "canonical_id": a.canonical_id, "rank": str(a.rank),
                 "product_id": str(a.product_id), "product_name": a.name,
                 "pack_units": str(a.pack_units), "match": a.match,
                 "last_price_eur": f"{a.price:.2f}" if a.price is not None else "",
                 "mapped_on": date.today().isoformat()})
    store.save_mapping(rows)
    print(f"{a.canonical_id} rank {a.rank} -> {a.shop} {a.product_id} ({a.name}, pack_units={a.pack_units}, {a.match})")
    return 0


def remove(a: argparse.Namespace) -> int:
    rows = store.load_mapping()
    keep = [m for m in rows
            if not (m["shop"] == a.shop and m["canonical_id"] == a.canonical_id and int(m["rank"]) == a.rank)]
    store.save_mapping(keep)
    print(f"removed {len(rows) - len(keep)} mapping(s)")
    return 0


def record_price(a: argparse.Namespace) -> int:
    rows = store.load_mapping()
    hit = 0
    for m in rows:
        if m["shop"] == a.shop and m["product_id"] == str(a.product_id):
            m["last_price_eur"] = f"{a.eur:.2f}"
            hit += 1
    store.save_mapping(rows)
    print(f"price {a.eur:.2f} recorded on {hit} mapping(s)")
    return 0 if hit else 1


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("show"); s.add_argument("ids", nargs="+"); s.add_argument("--shop", default="knuspr")
    s = sub.add_parser("set"); s.add_argument("canonical_id"); s.add_argument("--rank", type=int, default=0)
    s.add_argument("--product-id", type=int, required=True); s.add_argument("--name", required=True)
    s.add_argument("--pack-units", type=int, default=1); s.add_argument("--match", required=True)
    s.add_argument("--price", type=float); s.add_argument("--shop", default="knuspr")
    s = sub.add_parser("remove"); s.add_argument("canonical_id"); s.add_argument("--rank", type=int, default=0)
    s.add_argument("--shop", default="knuspr")
    s = sub.add_parser("price"); s.add_argument("product_id", type=int); s.add_argument("eur", type=float)
    s.add_argument("--shop", default="knuspr")
    a = ap.parse_args(argv[1:])
    return {"show": lambda: show(a.ids, a.shop), "set": lambda: set_mapping(a),
            "remove": lambda: remove(a), "price": lambda: record_price(a)}[a.cmd]()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
