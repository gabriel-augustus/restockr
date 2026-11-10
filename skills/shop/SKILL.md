---
name: shop
description: Turn the user's grocery list (e.g. an Apple Reminders list like "milk", "eggs x2") into a planned cart of their usual products, learning their wording over time. Use when the user sends a shopping/grocery list or asks Restockr to restock, plan a cart, or do the weekly shop. Never places an order.
---

# Shopping run

**Restockr never places, confirms or pays for an order.** The user always taps Buy.
Right now this skill only produces a **dry-run cart**; it does not touch any shop.

Scripts: `${CLAUDE_PLUGIN_ROOT}/scripts/catalog.py`, run with `uv run`. Data: `~/Restockr/`.

## 1. Resolve every list item

Split the list into items. Pull an explicit amount out of an item ("eggs x2",
"2 milk") as a one-off quantity for this run; look up the rest of the text.

```
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/catalog.py lookup "milk" "eggs" "brot"
```

- `KNOWN`: use that product. Quantity, in this order: the explicit amount on the list,
  the chosen option's quantity, the alias's quantity.
  `qty=ASK` means nobody has said how many yet: ask, then save it (step 3).
- `options=`: ranked choices (1 = first). Use option 1; fall back to the next one only
  when the shop doesn't have it. Each option may carry its own quantity (e.g. 8 x 1.5 L
  but 6 x 2 L). An option without a brand means "anything similar".
- `UNKNOWN`: **always ask, never guess and save silently.** This applies even when the
  answer looks obvious, and even when a similar alias exists ("Milch" vs "milk"): the
  household writes the same thing different ways, in more than one language, and every
  spelling gets confirmed once.

The goal is fewer questions every week: the catalog gets richer with the user's
preferences, so the same wording is never asked about twice.

## 2. Ask about all unknown items in one message

For each unknown item, offer the likely candidates from `~/Restockr/products.csv`
(spec, preferred brand, options, last price) plus "something new". Ask:
1. Which product (or a new one: what exactly, size, brand or "store brand / cheapest")?
2. Default quantity when the list just says the word?
3. A second or third choice if the first is sold out (optional)?
4. Should this exact wording always mean that? (yes = save alias)

Include every `qty=ASK` item in the same message. Use the AskUserQuestion tool when
there are only a few items; otherwise one grouped message.

## 3. Turn the answers into structured data

Save **what the answer means, not what was said.** "Usual bread" answered with
"wholegrain from Brand X, 500 g, one loaf, or any wholegrain if they're out" becomes:
an alias `usual bread` → `wholegrain-bread` with quantity 1, a product with spec
`Wholegrain bread, sliced, 500 g`, option 1 `Brand X wholegrain 500 g` (brand Brand X),
option 2 `Any wholegrain bread, 500 g`. Never paste the user's reply into `notes`;
`notes` is only for short flags like `CHECK size`.

```
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/catalog.py alias "<list wording>" <canonical_id> --quantity N
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/catalog.py option <canonical_id> <rank> --desc "<product, size>" \
  [--brand "<brand>"] [--size "<size>"] [--quantity N]
```

If the user doesn't give a quantity, save the alias without `--quantity` (it stays ASK).

For a product that doesn't exist yet, create it first:

```
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/catalog.py product <new-id> --spec "<generic spec with size>" \
  --category <category> --brand-policy exact|store_brand_or_cheapest|any [--preferred-brand "<brand>"]
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/build_products.py
```

Several aliases may point to the same product. Never delete or overwrite an existing
alias without asking.

## 4. Show the planned cart

A table: list wording → product (option chosen, brand rule) → quantity → last price →
cheapest price ever paid. State clearly that nothing was added to any shop cart yet.

## Brand policy (applies when a shop is connected)

Ranked options come first; the brand policy decides what happens when there are none
or none is available:

- `exact`: only `preferred_brand`. If the shop doesn't have it, report it; don't substitute.
- `store_brand_or_cheapest`: the shop's own brand matching the spec, else the cheapest
  match. Supermarket own brands (ja!, REWE Beste Wahl…) never exist elsewhere: that's fine.
- `any`: anything matching the spec; prefer what was bought before.

Price comparison per item: today's price vs `last_price_eur` and vs `cheapest_price_eur`.
