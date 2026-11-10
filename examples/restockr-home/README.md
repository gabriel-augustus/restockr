# Example data directory

What `~/Restockr/` looks like after importing some receipts, assigning products and
answering a few shopping-list questions. All data here is made up.

Try the scripts against it without touching your own data:

```
RESTOCKR_HOME=examples/restockr-home uv run scripts/build_products.py
RESTOCKR_HOME=examples/restockr-home uv run scripts/catalog.py lookup "milk" "wasser" "nudeln" "bread"
```

| File | Written by | What it holds |
|---|---|---|
| `variants.csv` | importers (counts, prices) + you/Claude (`canonical_id`, `notes`) | One row per product name exactly as a shop printed it. `canonical_id` says which product it is, or `skip`. |
| `products.csv` | you/Claude (`generic_spec` … `notes`) + `build_products.py` (the rest) | One row per product you actually restock. |
| `aliases.csv` | `catalog.py alias` | Shopping-list words → product + default quantity. Several words can point to one product. An empty quantity means "ask the first time". |
| `options.csv` | `catalog.py option` | Ranked choices per product: 1st choice, then fallbacks if it's sold out. Each can have its own size and quantity. |
| `history/imported_orders.txt` | importers | IDs of receipts already counted, so re-imports don't double-count. Nothing else. |

## Columns worth knowing

- `generic_spec`: brand-neutral description with size (`Fresh milk, 1 L, 3.5%`). Used to
  find the same product at another shop or in another country.
- `brand_policy`:
  - `exact`: only `preferred_brand`. If the shop doesn't have it, it gets reported, not swapped.
  - `store_brand_or_cheapest`: the shop's own brand, or the cheapest item matching the spec.
    Use it for supermarket own brands (`ja!` exists only at REWE).
  - `any`: anything matching the spec, preferring what was bought before.
- `last_price_eur` / `cheapest_price_eur`: the only price history kept. Enough to say
  "€0.10 more than last time, €0.30 above the cheapest you have paid".
- `status`: `ok`, `needs_spec`, `needs_policy`, `tie` (brand matters and two variants are
  bought equally often), or `manual` (added by hand, no purchase history yet).
