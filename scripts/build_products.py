# /// script
# requires-python = ">=3.10"
# ///
"""Roll variants.csv up into canonical products -> ~/Restockr/products.csv.

Usage:
  uv run build_products.py [--todo]

Variants sharing a canonical_id become one product. canonical_id "skip" is
ignored; empty canonical_id is reported as unassigned (--todo lists them).

Judgment columns in products.csv (generic_spec, category, brand_policy,
preferred_brand, ean, notes) are kept across rebuilds; everything else is
recomputed. Products with no variants (added by hand) are kept as "manual".

status:
  ok            nothing to do
  needs_spec    no generic_spec yet
  needs_policy  brand_policy missing or invalid
  tie           brand_policy=exact, no preferred_brand, and two variants are
                bought equally often: the user must pick
  manual        no purchase history (added by hand)
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import store  # noqa: E402


def _rank(v: dict) -> tuple:
    return (int(v["times_bought"] or 0), int(v["total_quantity"] or 0))


def build_products(variants: list[dict], previous: list[dict]) -> tuple[list[dict], list[str]]:
    judged = {p["canonical_id"]: p for p in previous}
    by_canon: dict[str, list[dict]] = defaultdict(list)
    for v in variants:
        cid = v["canonical_id"].strip()
        if cid and cid != store.SKIP:
            by_canon[cid].append(v)

    warnings: list[str] = []
    products = []
    for cid in sorted(set(by_canon) | set(judged)):
        prev = judged.get(cid, {})
        p = {"canonical_id": cid, **{f: prev.get(f, "") for f in store.PRODUCT_JUDGMENT_FIELDS}}
        vs = sorted(by_canon.get(cid, []), key=_rank, reverse=True)
        bought = [v for v in vs if v["last_bought"]]

        if bought:
            latest = max(bought, key=lambda v: v["last_bought"])
            p.update(
                times_bought=sum(int(v["times_bought"]) for v in vs),
                total_quantity=sum(int(v["total_quantity"]) for v in vs),
                first_bought=min(v["first_bought"] for v in bought),
                last_bought=latest["last_bought"],
                last_price_eur=latest["last_price_eur"],
                cheapest_price_eur=f"{min(float(v['cheapest_price_eur']) for v in bought):.2f}",
            )
        else:
            p.update(times_bought=0, total_quantity=0)
        p["top_variant"] = f"{vs[0]['source']}:{vs[0]['product_name']}" if vs else ""
        p["variants"] = " | ".join(f"{v['source']}:{v['product_name']}" for v in vs)

        status = "ok" if vs else "manual"
        if not p["generic_spec"].strip():
            status = "needs_spec"
            warnings.append(f"{cid}: no generic_spec")
        elif p["brand_policy"] not in store.BRAND_POLICIES:
            status = "needs_policy"
            warnings.append(f"{cid}: brand_policy {p['brand_policy']!r} not one of {store.BRAND_POLICIES}")
        elif (p["brand_policy"] == "exact" and not p["preferred_brand"].strip()
              and len(vs) > 1 and _rank(vs[0]) == _rank(vs[1])):
            status = "tie"
            warnings.append(f"{cid}: tie between {vs[0]['product_name']!r} and "
                            f"{vs[1]['product_name']!r}; set preferred_brand")
        p["status"] = status
        products.append(p)

    products.sort(key=lambda p: (-int(p["times_bought"]), p["canonical_id"]))
    return products, warnings


def main(argv: list[str]) -> int:
    variants = store.load_variants()
    products, warnings = build_products(variants, store.load_products())
    store.save_products(products)
    unassigned = [v for v in variants if not v["canonical_id"].strip()]
    skipped = sum(v["canonical_id"].strip() == store.SKIP for v in variants)
    print(f"{len(products)} products -> {store.data_dir() / 'products.csv'} "
          f"({len(variants)} variants: {skipped} skipped, {len(unassigned)} unassigned)")
    for w in warnings:
        print(f"  ! {w}")
    if "--todo" in argv:
        for v in unassigned:
            print(f"  ? {v['source']}\t{v['product_name']}\tx{v['times_bought']}\t{v['last_price_eur']} EUR")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
