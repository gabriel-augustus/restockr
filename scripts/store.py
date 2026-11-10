"""Restockr storage interface.

Every read/write of user data goes through this module, so the backend can be
swapped later (CSV today; SQLite or a cloud store later) without touching the
importers or skills.

Data lives in ~/Restockr/ (override with RESTOCKR_HOME), never in the plugin
folder: Claude Code replaces plugin folders on update.

Files:
  variants.csv                 one row per (source, product name as printed):
                               counts, last + cheapest price, and which canonical
                               product it belongs to
  products.csv                 canonical products: generic spec, brand policy,
                               rolled-up counts and prices
  aliases.csv                  shopping-list words -> canonical product + default qty
  history/imported_orders.txt  ids of receipts already counted (no items, no prices),
                               so re-importing never double-counts

Receipt-level history is deliberately NOT kept: only the last and the cheapest
price per variant. The original receipts (PDFs) stay wherever the user keeps them.
"""
from __future__ import annotations

import csv
import io
import os
import re
import tempfile
from pathlib import Path

SKIP = "skip"  # canonical_id meaning "not something I restock"

VARIANT_JUDGMENT_FIELDS = ["canonical_id", "notes"]
VARIANT_FIELDS = [
    "source", "product_name", "times_bought", "total_quantity",
    "first_bought", "last_bought", "last_price_eur", "cheapest_price_eur",
    *VARIANT_JUDGMENT_FIELDS,
]

# brand_policy values:
#   exact                    buy this brand (preferred_brand / top variant), nothing else
#   store_brand_or_cheapest  any shop's own brand, or the cheapest item matching the spec
#   any                      anything matching the spec; prefer what was bought before
BRAND_POLICIES = ("exact", "store_brand_or_cheapest", "any")
PRODUCT_JUDGMENT_FIELDS = [
    "generic_spec", "category", "brand_policy", "preferred_brand", "ean", "notes",
]
PRODUCT_COMPUTED_FIELDS = [
    "times_bought", "total_quantity", "first_bought", "last_bought",
    "last_price_eur", "cheapest_price_eur", "top_variant", "variants", "status",
]
PRODUCT_FIELDS = ["canonical_id", *PRODUCT_JUDGMENT_FIELDS, *PRODUCT_COMPUTED_FIELDS]

ALIAS_FIELDS = ["alias", "canonical_id", "quantity", "notes"]


def data_dir() -> Path:
    d = Path(os.environ.get("RESTOCKR_HOME", Path.home() / "Restockr")).expanduser()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path(name: str) -> Path:
    p = data_dir() / name
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _atomic_write(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    os.replace(tmp, path)


def _load_csv(name: str) -> list[dict]:
    p = _path(name)
    if not p.exists():
        return []
    with p.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _save_csv(name: str, fields: list[str], rows: list[dict]) -> None:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore", restval="")
    w.writeheader()
    w.writerows(rows)
    _atomic_write(_path(name), buf.getvalue())


# --- imported receipts ledger ---------------------------------------------

def load_imported_orders() -> set[str]:
    p = _path("history/imported_orders.txt")
    return set(p.read_text().split()) if p.exists() else set()


def save_imported_orders(ids: set[str]) -> None:
    _atomic_write(_path("history/imported_orders.txt"), "".join(f"{i}\n" for i in sorted(ids)))


# --- variants --------------------------------------------------------------

def load_variants() -> list[dict]:
    return _load_csv("variants.csv")


def save_variants(rows: list[dict]) -> None:
    rows = sorted(rows, key=lambda r: (-int(r["times_bought"] or 0), r["source"], r["product_name"]))
    _save_csv("variants.csv", VARIANT_FIELDS, rows)


def _c(eur: str) -> int | None:
    return round(float(eur) * 100) if eur not in ("", None) else None


def record_purchases(lines: list[dict]) -> tuple[int, int]:
    """Fold purchase lines into variants.csv, skipping receipts already counted.

    Each line: source, order_id, ordered_at (ISO), product_name, quantity,
    paid_cents (what the line cost after discounts). Only product lines.
    Returns (receipts_added, receipts_already_known).
    """
    done = load_imported_orders()
    variants = {(v["source"], v["product_name"]): v for v in load_variants()}
    new_orders: set[str] = set()
    known: set[str] = set()

    for l in sorted(lines, key=lambda l: l["ordered_at"]):
        oid = f"{l['source']}:{l['order_id']}"
        if oid in done:
            known.add(oid)
            continue
        new_orders.add(oid)
        v = variants.setdefault((l["source"], l["product_name"]), {
            "source": l["source"], "product_name": l["product_name"],
            "times_bought": "0", "total_quantity": "0", "first_bought": "", "last_bought": "",
            "last_price_eur": "", "cheapest_price_eur": "", "canonical_id": "", "notes": "",
        })
        day = l["ordered_at"][:10]
        unit_c = round(l["paid_cents"] / l["quantity"])
        v["_orders"] = v.get("_orders", set()) | {oid}
        v["total_quantity"] = str(int(v["total_quantity"]) + l["quantity"])
        if not v["first_bought"] or day < v["first_bought"]:
            v["first_bought"] = day
        if not v["last_bought"] or day >= v["last_bought"]:
            v["last_bought"], v["last_price_eur"] = day, f"{unit_c / 100:.2f}"
        cheapest = _c(v["cheapest_price_eur"])
        if cheapest is None or unit_c < cheapest:
            v["cheapest_price_eur"] = f"{unit_c / 100:.2f}"

    for v in variants.values():
        if "_orders" in v:
            v["times_bought"] = str(int(v["times_bought"]) + len(v.pop("_orders")))
    save_variants(list(variants.values()))
    save_imported_orders(done | new_orders)
    return len(new_orders), len(known)


def forget_source(source: str) -> None:
    """Zero a source's counts and ledger (keeps judgment columns). For re-imports
    after a parser fix."""
    rows = load_variants()
    for v in rows:
        if v["source"] == source:
            v.update(times_bought="0", total_quantity="0", first_bought="", last_bought="",
                     last_price_eur="", cheapest_price_eur="")
    save_variants(rows)
    save_imported_orders({o for o in load_imported_orders() if not o.startswith(f"{source}:")})


# --- products --------------------------------------------------------------

def load_products() -> list[dict]:
    return _load_csv("products.csv")


def save_products(rows: list[dict]) -> None:
    _save_csv("products.csv", PRODUCT_FIELDS, rows)


# --- aliases ---------------------------------------------------------------

def normalise_alias(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def load_aliases() -> list[dict]:
    return _load_csv("aliases.csv")


def save_aliases(rows: list[dict]) -> None:
    rows = sorted(rows, key=lambda r: (r["canonical_id"], r["alias"]))
    _save_csv("aliases.csv", ALIAS_FIELDS, rows)
