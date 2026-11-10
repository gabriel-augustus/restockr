# /// script
# requires-python = ">=3.10"
# ///
"""Shopping-list words -> products. Used by the shop skill.

Usage:
  uv run catalog.py lookup "milk" "Milch x2" ...
      For each item: KNOWN (alias -> product, spec, brand policy, default qty,
      last/cheapest price) or UNKNOWN. Matching is exact on the normalised
      alias (lowercase, single spaces). Fuzzy guessing is Claude's job, and
      Claude must ask the user before saving a new alias.

  uv run catalog.py alias "<alias>" <canonical_id> [--quantity N] [--notes TEXT]
      Save or update an alias. Several aliases may point to one product.

  uv run catalog.py product <canonical_id> --spec TEXT --category TEXT
          --brand-policy exact|store_brand_or_cheapest|any
          [--preferred-brand TEXT] [--notes TEXT]
      Create or update a product's judgment columns (e.g. something never bought
      at a shop yet). Run build_products.py afterwards.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import store  # noqa: E402


def lookup(items: list[str]) -> int:
    aliases = {a["alias"]: a for a in store.load_aliases()}
    products = {p["canonical_id"]: p for p in store.load_products()}
    for item in items:
        a = aliases.get(store.normalise_alias(item))
        if not a:
            print(f"UNKNOWN\t{item}")
            continue
        p = products.get(a["canonical_id"])
        if not p:
            print(f"BROKEN\t{item}\talias points to missing product {a['canonical_id']}")
            continue
        print(f"KNOWN\t{item}\t{p['canonical_id']}\tqty={a['quantity'] or 1}\t{p['generic_spec']}"
              f"\tpolicy={p['brand_policy']}"
              + (f"\tbrand={p['preferred_brand']}" if p["preferred_brand"] else "")
              + f"\tlast={p['last_price_eur'] or '-'}\tcheapest={p['cheapest_price_eur'] or '-'}")
    return 0


def save_alias(alias: str, cid: str, quantity: str, notes: str) -> int:
    if cid not in {p["canonical_id"] for p in store.load_products()}:
        print(f"No product {cid!r} in products.csv. Create it first (catalog.py product ...).")
        return 1
    key = store.normalise_alias(alias)
    rows = [a for a in store.load_aliases() if a["alias"] != key]
    rows.append({"alias": key, "canonical_id": cid, "quantity": quantity, "notes": notes})
    store.save_aliases(rows)
    print(f"alias {key!r} -> {cid} (qty {quantity})")
    return 0


def save_product(a: argparse.Namespace) -> int:
    if a.brand_policy not in store.BRAND_POLICIES:
        print(f"brand_policy must be one of {store.BRAND_POLICIES}")
        return 1
    rows = store.load_products()
    p = next((r for r in rows if r["canonical_id"] == a.canonical_id), None)
    if p is None:
        p = {"canonical_id": a.canonical_id}
        rows.append(p)
    p.update(generic_spec=a.spec, category=a.category, brand_policy=a.brand_policy)
    if a.preferred_brand is not None:
        p["preferred_brand"] = a.preferred_brand
    if a.notes is not None:
        p["notes"] = a.notes
    store.save_products(rows)
    print(f"product {a.canonical_id} saved; run build_products.py to refresh counts")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("lookup"); s.add_argument("items", nargs="+")
    s = sub.add_parser("alias"); s.add_argument("alias"); s.add_argument("canonical_id")
    s.add_argument("--quantity", default="1"); s.add_argument("--notes", default="")
    s = sub.add_parser("product"); s.add_argument("canonical_id")
    s.add_argument("--spec", required=True); s.add_argument("--category", required=True)
    s.add_argument("--brand-policy", required=True)
    s.add_argument("--preferred-brand"); s.add_argument("--notes")
    a = ap.parse_args(argv[1:])
    if a.cmd == "lookup":
        return lookup(a.items)
    if a.cmd == "alias":
        return save_alias(a.alias, a.canonical_id, a.quantity, a.notes)
    return save_product(a)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
