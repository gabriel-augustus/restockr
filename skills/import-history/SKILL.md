---
name: import-history
description: Import the user's grocery purchase history (currently REWE in-store eBon PDFs) and turn it into the list of canonical products they actually buy, in ~/Restockr/products.csv. Use when the user wants to set up Restockr, import receipts or order history, or rebuild their product list.
---

# Import purchase history → canonical products

Restockr's division of labour: **scripts count, Claude judges.** Never do arithmetic
or file parsing in your head; never let a script guess what a product is.

Scripts live in `${CLAUDE_PLUGIN_ROOT}/scripts/` and run with `uv run`. User data lives
in `~/Restockr/` (override: `RESTOCKR_HOME`). Never write user data into the plugin
folder, and never commit it. Read and write the CSVs through `store.py` or the scripts,
not by hand-rewriting them.

## What is stored (and what is not)

- `variants.csv`: one row per product name as a shop printed it, with times bought,
  first/last date, **last price and cheapest price**, and which product it belongs to.
- `products.csv`: canonical products. Judgment columns (yours/the user's):
  `generic_spec`, `category`, `brand_policy`, `preferred_brand`, `ean`, `notes`.
  Everything else is recomputed by `build_products.py`.
- `history/imported_orders.txt`: receipt ids already counted. Nothing else.
- Individual receipt lines and full price history are **not** kept, by design.

## Pipeline

1. **Import** (script). Supported sources:
   - REWE in-store eBons (PDFs exported from the REWE app):
     `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/import_rewe_ebons.py "<folder>"`
   Every receipt is checked against its SUMME total. If a receipt fails, show the error;
   fix the parser (add a fake fixture + test), then re-run with `--reset`. Never fudge data.

2. **Assign variants** (you). `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/build_products.py --todo`
   lists variants without a `canonical_id`. For each, set in `variants.csv`:
   - `canonical_id`: short kebab-case id. Spelling/brand variants of the same thing share
     one id. Different sizes or flavours that matter to the user get different ids.
   - `skip` for non-restock items (bags, one-offs). Bought once and not clearly part of a
     repeat product → `skip` with note `bought once; set a canonical_id to keep it`.

3. **Describe new products** (you), with
   `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/catalog.py product <id> --spec ... --category ... --brand-policy ...`:
   - `generic_spec`: always with size, e.g. `Rolled oats, 500 g`. This is what matches
     across shops and countries. REWE till names have no size: infer it from name and
     price and add `CHECK size` to notes. If you can't tell what it is, leave the spec
     empty and ask the user. Do not invent.
   - `brand_policy`:
     - `exact`: the brand is the point (set `preferred_brand`).
     - `store_brand_or_cheapest`: the shop's own brand (ja!, K-Classic, Knuspr's own…)
       or the cheapest item matching the spec. Default for supermarket own brands, since
       those don't exist at other shops.
     - `any`: anything matching the spec; prefer what was bought before.
   - `category`: dairy, cheese, eggs, bakery, meat & fish, ready meals, frozen, produce,
     pantry, snacks & sweets, drinks, beer, household, seasonal.

4. **Build**: `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/build_products.py`. Then ask the user,
   in one grouped message, about everything flagged (`needs_spec`, `needs_policy`, `tie`)
   and every `CHECK` note. Save the answers and rebuild.

## Not in scope here

Shopping-list aliases (the `shop` skill), matching products to Knuspr or other shops,
and anything that touches a cart or checkout.
