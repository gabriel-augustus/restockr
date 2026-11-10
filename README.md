# Restockr

Restockr is a Claude plugin that turns a grocery list into a filled online shopping
cart, using the products you actually buy. You write "milk"; Restockr knows that means
two 1 L cartons of the milk you always get, puts them in the cart, and tells you how
the price compares with what you paid before.

**It never places the order.** It stops at the cart. You review it, pay and tap Buy in
the shop's own app or website.

Status: early alpha (v0.1), built for personal use first and developed in the open.

## How it works

There is no app. Restockr is a set of skills, scripts and an MCP connection that run
inside Claude.

1. **Your list.** You keep a grocery list wherever you like; the target is Apple
   Reminders, filled by voice through Siri during the week.
2. **A run.** You ask Claude to do the shopping. Restockr reads the list and resolves
   each item to one of your products through an alias table ("milk", "Milch" and
   "h-milch" can all point to the same product).
3. **Questions only when needed.** Wording it hasn't seen before gets a question (which
   product, how many, which brand), and the answer is saved so it's never asked twice.
4. **The cart.** It clears the shop's cart, fills it, and reports the total, price
   changes against your last and cheapest price, what was out of stock, and what it
   couldn't map.

The design rule throughout: scripts do parsing, counting and arithmetic; Claude does
the judgment calls (what "SAUERKR.MILD" on a receipt is, whether two items are the
same product).

## Shops: Knuspr first

v0.1 talks to exactly one shop: **[Knuspr](https://www.knuspr.de)**, through its
official MCP server (`https://mcp.knuspr.de/mcp`). That means it works in any country
where Knuspr operates, as long as Knuspr delivers to your postcode. Other shops come
later (see the roadmap).

Knuspr's MCP server supports OAuth 2.1 with PKCE and dynamic client registration, so
you log in on Knuspr's own page and Claude stores only a revocable token. Restockr never
sees or stores your password.

## Never buys

Two layers make sure Restockr can't check out:

- The skills never ask for it.
- A `PreToolUse` hook (`hooks/never_buy.py`) runs before every Knuspr tool call and
  denies anything that looks like checkout, ordering or payment. If it can't read the
  call, it denies it.

## What works today

| Piece | State |
|---|---|
| Import purchase history from REWE in-store eBons (PDF receipts from the REWE app) | Works |
| Product catalog: generic spec, brand policy, last and cheapest price | Works |
| Shopping-list aliases, asking once per new wording | Works (dry run: plans the cart, doesn't touch a shop) |
| Knuspr connection (OAuth) + never-buy hook | Connected; real tool names not yet on the deny list |
| Filling the Knuspr cart, matching products to Knuspr | Not started |
| Reading Apple Reminders | Not started |

## Install

Requires [Claude Code](https://claude.com/claude-code) and
[`uv`](https://docs.astral.sh/uv/) (`brew install uv`).

```
/plugin marketplace add gabriel-augustus/restockr
/plugin install restockr@restockr
```

Then run `/mcp`, pick `plugin:restockr:knuspr`, choose Authenticate and log in to Knuspr.

## Data

Your data lives in `~/Restockr/` (override with `RESTOCKR_HOME`), outside the plugin
folder, because Claude Code replaces plugin folders on update. Nothing personal is ever
written into this repo.

What is kept, on purpose, is small: per product, how often you bought it, the last
price and the cheapest price. Individual receipts and full price history are not stored.

See [`examples/restockr-home/`](examples/restockr-home/) for a complete example data
directory with made-up data and an explanation of every file and column.

## Layout

```
.claude-plugin/   plugin.json (incl. the Knuspr MCP server), marketplace.json
skills/           import-history, shop
scripts/          store.py (all data access), import_rewe_ebons.py, build_products.py, catalog.py
hooks/            never_buy.py + hooks.json
examples/         example data directory
tests/            pytest, fake fixtures only
```

## Development

```
git clone https://github.com/gabriel-augustus/restockr
claude --plugin-dir ./restockr
uv run --with pytest --with pypdf pytest tests/
```

## Roadmap

Each release builds on the previous one. Anyone who wants something from a later
release is welcome to build it.

| Release | Goal | Why in this order |
|---|---|---|
| v0.1 Feed Me | A real Knuspr cart from a list | Solves the core problem |
| v0.2 No Surprises | Carts that survive stock-outs and new items | Those break v0.1 within weeks |
| v0.3 Moving Day | Change country without rebuilding your product list | Depends on generic specs from v0.1 |
| v0.4 It Remembers | Price memory and habits | Needs a few runs of history first |
| v0.5 Hands-Free | Voice, schedules, notifications | Only worth it once a run can go unwatched |
| v0.6 Shop Around | More shops, split orders | Biggest savings, most fragile integration work |
| v0.7 Cook Club | Recipes | Nice to have |
| v1.0 For Everyone | Setup without knowing what MCP is | Only once it works well for a few people |

### v0.1 Feed Me

- Build the product catalog from order history: the most-bought variant wins, ties get
  a question. (Today: REWE eBons.)
- Store a generic spec next to every product, e.g. "UHT milk, 1 L, 3.5%", for
  cross-shop and cross-country matching.
- Catalog stays editable by hand.
- Read the list from Apple Reminders.
- Clear the Knuspr cart, then fill it with default quantities.
- Price check at other shops: product prices only, no delivery fees.
- Report: total, out of stock, unmapped items.
- Never buys.

Not in v0.1: price history, Siri, schedules, substitutes.

### v0.2 No Surprises

- Up to 3 ranked substitutes per product, used when the first choice is sold out.
- Unmapped items handled during the run: pick an option or describe it, saved for next time.
- Quantities on the list ("2 milk") override defaults.
- Stop if the cart is below the shop's minimum order.
- Show the cheapest delivery slot.

### v0.3 Moving Day

- New postcode: find the shops that deliver there and switch connectors.
- Match each product to a local equivalent by its generic spec.
- New matches stay marked as trial until you've bought them and kept or dropped them.
- The previous country's catalog is kept.

### v0.4 It Remembers

- History of every run: items, total, and whether you ordered it.
- Price changes against what you last paid.
- Staples that are always added.
- "You usually buy coffee, add it?" suggestions.
- Pick the bigger pack or multi-buy when it costs the same or less.

### v0.5 Hands-Free

- "Hey Siri, do my grocery shopping" starts a run.
- Scheduled runs, e.g. every Friday morning.
- A notification when it's done.
- Fast mode: no questions, every call made automatically, fastest delivery picked.

### v0.6 Shop Around

- Choose a default shop from the ones that deliver to you.
- Carts at shops without an MCP server, built through the browser (Claude in Chrome).
- Split the order when a lot is missing at the main shop or roughly 30% is cheaper elsewhere.

### v0.7 Cook Club

- Save recipes with ingredients mapped to your products.
- "Cooking A, B and C this week" adds what's missing to the list.
- After a run, show which saved recipes the groceries cover.

### v1.0 For Everyone

- Guided onboarding: import order history or upload an existing product spreadsheet.
- Other list sources: Alexa (through a list app), Android.
- Setup docs for people who aren't engineers.
