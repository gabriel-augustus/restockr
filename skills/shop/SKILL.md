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

- `KNOWN`: use that product. Quantity = the explicit amount on the list, otherwise
  the alias's default `qty`.
- `UNKNOWN`: **always ask, never guess and save silently.** This applies even when the
  answer looks obvious, and even when a similar alias exists ("Milch" vs "milk"): the
  user writes the same thing different ways, and every spelling gets confirmed once.

## 2. Ask about all unknown items in one message

For each unknown item, offer the likely candidates from `~/Restockr/products.csv`
(spec, preferred brand, last price) plus "something new". Ask:
1. Which product (or a new one: what exactly, size, brand or "store brand / cheapest")?
2. Default quantity when the list just says the word?
3. Should this exact wording always mean that? (yes = save alias)

Use the AskUserQuestion tool when there are only a few items; otherwise one grouped
message.

## 3. Save the answers so you never ask again

```
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/catalog.py alias "<list wording>" <canonical_id> --quantity N
```

For a product that doesn't exist yet, create it first:

```
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/catalog.py product <new-id> --spec "<generic spec with size>" \
  --category <category> --brand-policy exact|store_brand_or_cheapest|any [--preferred-brand "<brand>"]
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/build_products.py
```

Several aliases may point to the same product. Never delete or overwrite an existing
alias without asking.

## 4. Show the planned cart

A table: list wording → product (spec, brand rule) → quantity → last price → cheapest
price ever paid. State clearly that nothing was added to any shop cart yet.

## Brand policy (applies when a shop is connected)

- `exact`: only `preferred_brand`. If the shop doesn't have it, report it; don't substitute.
- `store_brand_or_cheapest`: the shop's own brand matching the spec, else the cheapest
  match. Supermarket own brands (ja!, REWE Beste Wahl…) never exist elsewhere: that's fine.
- `any`: anything matching the spec; prefer what was bought before.

Price comparison per item: today's price vs `last_price_eur` and vs `cheapest_price_eur`.
