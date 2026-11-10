# /// script
# requires-python = ">=3.10"
# dependencies = ["pypdf>=4"]
# ///
"""Import REWE in-store eBons (PDF receipts) into ~/Restockr/variants.csv.

Usage:
  uv run import_rewe_ebons.py <folder-with-pdfs> [--reset]

Deterministic parsing only: no guessing what "SAUERKR.MILD" is. That is
Claude's job, in variants.csv / products.csv. Every receipt is checked: the
parsed lines must add up to the receipt's SUMME, or it is reported and skipped.
Safe to re-run: receipts already counted are skipped. --reset forgets all REWE
counts first (keeps your canonical_id/notes), for re-importing after a parser fix.
Receipt lines themselves are not stored; only counts, last and cheapest price.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import store  # noqa: E402

SOURCE = "rewe_store"

BODY_START = re.compile(r"^\s*EUR\s*$")
SUMME = re.compile(r"^\s*SUMME\s+EUR\s+(-?\d+,\d{2})\s*$")
ITEM = re.compile(
    r"^(?P<indent>\s*)(?P<name>\S.*?)\s+(?P<amount>-?\d+,\d{2})\s+(?P<tax>[AB])(?P<star>\s*\*)?\s*$"
)
QTY = re.compile(r"^\s*(?P<n>\d+)\s+Stk\s+x\s+(?P<price>-?\d+,\d{2})\s*$")
WEIGHT = re.compile(r"^\s*Handeingabe E-Bon\s+(?P<kg>\d+,\d+)\s*kg\s*$")
FOOTER = re.compile(r"(\d{2}\.\d{2}\.\d{4})\s+(\d{2}:\d{2})\s+Bon-Nr\.?:\s*(\d+)")
MARKT = re.compile(r"Markt:\s*(\d+)")


class ParseError(Exception):
    pass


def cents(s: str) -> int:
    return int(s.replace(",", "").replace(".", ""))


def eur(c: int) -> float:
    return round(c / 100, 2)


def classify(name: str) -> str:
    n = name.upper()
    if n.startswith("PFAND"):
        return "deposit"
    if n.startswith("LEERG"):
        return "deposit_return"
    return "product"


def parse_ebon_text(text: str) -> list[dict]:
    """Parse the text of one eBon into normalised order lines. Raises ParseError."""
    lines = text.splitlines()

    footer = next((m for l in lines if (m := FOOTER.search(l))), None)
    markt = next((m.group(1) for l in lines if (m := MARKT.search(l))), None)
    if not footer or not markt:
        raise ParseError("no date/Bon-Nr/Markt footer found")
    date_s, time_s, bon = footer.groups()
    ordered_at = datetime.strptime(f"{date_s} {time_s}", "%d.%m.%Y %H:%M").isoformat()
    order_id = f"{markt}-{ordered_at[:10]}-{bon}"

    try:
        start = next(i for i, l in enumerate(lines) if BODY_START.match(l))
    except StopIteration:
        raise ParseError("no item section (EUR header) found")

    items: list[dict] = []
    summe = None
    for raw in lines[start + 1:]:
        if m := SUMME.match(raw):
            summe = cents(m.group(1))
            break
        if not raw.strip() or set(raw.strip()) <= {"-", "="}:
            continue
        if m := QTY.match(raw):
            if not items:
                raise ParseError(f"quantity line before any item: {raw!r}")
            it = items[-1]
            n, price = int(m["n"]), cents(m["price"])
            # Returned empties print a positive unit price under a negative total.
            if n * abs(price) != abs(it["_amount"]):
                raise ParseError(f"{it['product_name']}: {n} x {price} != {it['_amount']}")
            price = abs(price) if it["_amount"] >= 0 else -abs(price)
            it["quantity"], it["_unit"] = n, price
            it["raw"] += "\n" + raw.strip()
            continue
        if m := WEIGHT.match(raw):
            if not items:
                raise ParseError(f"weight line before any item: {raw!r}")
            items[-1]["weight_kg"] = float(m["kg"].replace(",", "."))
            items[-1]["raw"] += "\n" + raw.strip()
            continue
        if m := ITEM.match(raw):
            amount = cents(m["amount"])
            name = m["name"].strip()
            # Indented negative line = discount on the item above it.
            if m["indent"] and amount < 0 and items and items[-1]["kind"] == "product":
                items[-1]["_discount"] += amount
                items[-1]["raw"] += "\n" + raw.strip()
                continue
            items.append({
                "product_name": name, "kind": classify(name), "quantity": 1,
                "_amount": amount, "_unit": amount, "_discount": 0,
                "weight_kg": None, "raw": raw.strip(),
            })
            continue
        raise ParseError(f"unrecognised line: {raw!r}")

    if summe is None:
        raise ParseError("no SUMME line found")
    total = sum(it["_amount"] + it["_discount"] for it in items)
    if total != summe:
        raise ParseError(f"lines add up to {eur(total)} but SUMME is {eur(summe)}")

    out = []
    for it in items:
        out.append({
            "source": SOURCE, "order_id": order_id, "ordered_at": ordered_at,
            "product_name": it["product_name"], "brand": None,
            "size_value": None, "size_unit": None,
            "quantity": it["quantity"], "unit_price_eur": eur(it["_unit"]),
            "ean": None, "shop_product_id": None, "raw": it["raw"],
            "kind": it["kind"], "line_total_eur": eur(it["_amount"]),
            "discount_eur": eur(it["_discount"]), "weight_kg": it["weight_kg"],
            "store_id": markt,
        })
    return out


def pdf_text(path: Path) -> str:
    from pypdf import PdfReader
    return "\n".join(p.extract_text() or "" for p in PdfReader(path).pages)


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if a != "--reset"]
    if len(args) != 1:
        print(__doc__)
        return 2
    folder = Path(args[0]).expanduser()
    pdfs = sorted(folder.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs in {folder}")
        return 1

    all_lines, failed, seen = [], [], {}
    for pdf in pdfs:
        try:
            lines = parse_ebon_text(pdf_text(pdf))
        except ParseError as e:
            failed.append((pdf.name, str(e)))
            continue
        oid = lines[0]["order_id"] if lines else None
        if oid in seen:
            print(f"duplicate receipt: {pdf.name} is the same as {seen[oid]} (skipped)")
            continue
        seen[oid] = pdf.name
        all_lines += lines

    if "--reset" in argv:
        store.forget_source(SOURCE)
    products = [{
        "source": l["source"], "order_id": l["order_id"], "ordered_at": l["ordered_at"],
        "product_name": l["product_name"], "quantity": l["quantity"],
        "paid_cents": round((l["line_total_eur"] + l["discount_eur"]) * 100),
    } for l in all_lines if l["kind"] == "product"]
    added, known = store.record_purchases(products)
    print(f"Parsed {len(seen)} receipts from {len(pdfs)} PDFs ({len(products)} product lines).")
    print(f"New receipts counted: {added}, already counted: {known}. "
          f"-> {store.data_dir() / 'variants.csv'}")
    if failed:
        print(f"\n{len(failed)} receipt(s) FAILED and were not imported:")
        for name, err in failed:
            print(f"  {name}: {err}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
