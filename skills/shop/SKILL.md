---
name: shop
description: Do the grocery shopping run - read the grocery list (Apple Reminders or a list in chat), resolve each item to the user's usual product, match it to a Knuspr product, fill the Knuspr cart and report prices. Learns the user's wording and preferences over time. Use when the user asks to do the shopping, restock, fill the cart or sends a grocery list. Never places, confirms or pays for an order.
---

# Shopping run

**Restockr never places, confirms or pays for an order.** It fills the cart and hands
over the checkout link; the user reviews, pays and taps Buy. A hook blocks every Knuspr
tool except reading and cart editing; don't try to work around a block.

Scripts live in `${CLAUDE_PLUGIN_ROOT}/scripts/` and run with `uv run`. Data: `~/Restockr/`.
Scripts do lookups and arithmetic; you do judgment and ask questions. Never compute
quantities or totals yourself: use `cart.py`.

Every Knuspr call takes a `context` argument: one short sentence about the goal, with
no personal data (no names, addresses, list items).

## 1. Get the list

- The user pasted a list → use it.
- Otherwise read Apple Reminders (macOS only):
  `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/reminders.py items`
  - `NO_LIST_CONFIGURED` → run `reminders.py lists`, ask which list is the grocery
    list, save it with `reminders.py use "<name>"`.
  - Permission error → tell the user to allow access in System Settings > Privacy &
    Security > Reminders, then retry.
  Reminders is read-only: never tick or delete items.

Split each item into wording + optional explicit amount ("eggs x2", "2 milk",
"leite x3"): the amount is a one-off for this run.

## 2. Resolve wording to products

```
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/catalog.py lookup "<item>" "<item>" ...
```

- `KNOWN`: the product. `options=` are ranked choices (1 = first). Quantity, in order:
  the explicit amount on the list, option 1's quantity, the alias's quantity.
  `qty=ASK` = nobody said how many yet → ask (step 3).
- `UNKNOWN`: **always ask, never guess and save silently**, even when it looks obvious
  or a similar alias exists. The household writes the list in several languages and
  spellings; each one is confirmed once, then saved as its own alias.

## 3. Ask once, in one message

Collect everything that needs the user and ask in one go (AskUserQuestion for a few
items, otherwise one grouped message):
- unknown wording: which product (offer 2-3 candidates from `~/Restockr/products.csv`
  plus "something new"), how many by default, a 2nd/3rd choice if sold out, and
  whether this wording should always mean that;
- `qty=ASK` items: how many by default;
- unmapped products without a direct Knuspr equivalent (step 4).

**Turn answers into structured data, not text.** "Usual bread" answered with
"wholegrain from Brand X, 500 g, one loaf, or any wholegrain if they're out" becomes an
alias `usual bread` → `wholegrain-bread` with quantity 1, a product spec
`Wholegrain bread, sliced, 500 g`, option 1 `Brand X wholegrain 500 g` (brand Brand X),
option 2 `Any wholegrain bread, 500 g`. Never paste a reply into `notes`.

```
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/catalog.py product <id> --spec "<spec with size>" \
  --category <category> --brand-policy exact|store_brand_or_cheapest|any [--preferred-brand "<brand>"]
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/catalog.py alias "<wording>" <id> [--quantity N]
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/catalog.py option <id> <rank> --desc "<product, size>" \
  [--brand "<brand>"] [--size "<size>"] [--quantity N]
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/build_products.py
```

No quantity given → save the alias without `--quantity` (stays ASK). Never overwrite or
delete an alias, option or mapping without asking.

## 4. Match to Knuspr, reactively

Only the products on this list are matched; the mapping grows one list at a time.

```
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/mapping.py show <id> <id> ...
```

For each `UNMAPPED` line, search Knuspr (`batch_search_products`, up to 4 queries per
call, German keywords, e.g. brand + product + size). Search results are noisy: check
brand, product and size yourself, never take the first hit blindly. Knuspr has no EAN.

- **Direct equivalent → save without asking.** Same brand, product and size as the
  option (or, without options: matches the spec and the brand policy:
  `exact` = the preferred brand; `store_brand_or_cheapest` = Knuspr's own brand or the
  cheapest spec match; `any` = a close spec match).
- **Not direct** (other brand for `exact`, other size, other variant) → ask in step 3,
  offering up to 3 Knuspr candidates with price and size. Save the user's pick as
  `confirmed`. "Skip it this time" saves nothing.

```
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/mapping.py set <id> --rank <option rank or 0> \
  --product-id <knuspr id> --name "<knuspr name>" --pack-units <N> --match direct|confirmed
```

`--pack-units`: how many of the user's units one Knuspr product holds. The user counts
bottles and Knuspr sells `6x1,25 l` → 6. A single item → 1. If the unit is unclear
(is "2 yoghurts" two cups or two 4-packs?), ask.

## 5. Check stock, fall back through options

Call `get_product_details` for all mapped product ids at once. For each item use the
first option whose Knuspr product is available (`stock.availabilityStatus`); price =
`prices.salePrice` if set, else `prices.originalPrice` (never apply another discount).
Note `stock.maxAvailableAmount`. Nothing available → report it as out of stock.

## 6. Plan quantities (script)

Write one JSON object per item to a file in your scratchpad and run:

```
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/cart.py plan --min-order <minimalOrderPrice> < lines.json
```

(fields: item, canonical_id, units, product_id, product_name, pack_units, price_eur,
in_stock, max_available). It rounds packs up, caps at the shop limit, totals, checks
the minimum order and flags price changes. Use its `ADD_ITEMS` JSON as-is.

## 7. Fill the cart

1. `get_cart`. If it already has items, list them and ask: clear it first, or add on
   top? `clear_cart` only after a clear yes.
2. `add_items_to_cart` with the `ADD_ITEMS` list.
3. `get_cart` again: its total is the truth.
4. Record each price seen: `mapping.py price <product_id> <price>`.
5. `get_checkout_link` and give the user the link.

Never call checkout, payment, delivery-slot or order tools; the user does that in the
Knuspr app.

## 8. Report

A table: list wording → Knuspr product → quantity (say when packs were rounded up or
capped) → price → per-unit price vs last time at Knuspr and vs the cheapest ever paid
(REWE receipts; note when sizes differ). Then: cart total from `get_cart`, below the
minimum order or not, out of stock, items skipped, and what was learned this run (new
aliases, options, mappings). End with the checkout link.
