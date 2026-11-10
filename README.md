# Restockr

A Claude Code plugin that turns your grocery list into a filled
[Knuspr](https://www.knuspr.de) cart, using the products you actually buy.
"milk" on your list becomes the milk you always get, in your usual amount.

**It never places the order.** It stops at the cart; you check out yourself.

Early alpha (v0.1).

## Requirements

- [Claude Code](https://claude.com/claude-code)
- [`uv`](https://docs.astral.sh/uv/): `brew install uv`
- A Knuspr account. Restockr works in any country where Knuspr operates, as long as
  Knuspr delivers to your postcode.

## Install

```
/plugin marketplace add gabriel-augustus/restockr
/plugin install restockr@restockr
```

## Connect Knuspr

Run `/mcp`, pick `plugin:restockr:knuspr`, choose **Authenticate** and log in on
Knuspr's own page.

Knuspr's MCP server supports OAuth, so your email and password never go into a config
file, an environment variable or a request header. Claude Code only keeps a token you
can revoke.

## Use

Ask Claude in plain words:

- **"Import my REWE eBons from `<folder>`"**: builds your product list from REWE
  receipt PDFs (exported from the REWE app).
- **"Plan my grocery shopping: milk, eggs x2, coffee"**: matches each item to one of
  your products. Wording it hasn't seen yet gets a question once, and the answer is
  remembered.

## Your data

Stays on your machine in `~/Restockr/` (set `RESTOCKR_HOME` to change it). Only
product counts, the last price and the cheapest price are kept. See
[`examples/restockr-home/`](examples/restockr-home/) for what the files look like.

## Never buys

A hook blocks every Knuspr tool that looks like checkout, ordering or payment before it
runs.

## Status

| Feature | State |
|---|---|
| Product list from REWE eBons | Works |
| Shopping list → planned cart | Works (dry run, no shop calls yet) |
| Knuspr login (OAuth) | Works |
| Filling the Knuspr cart | Not yet |
| Reading Apple Reminders | Not yet |

## Roadmap

| Release | Goal |
|---|---|
| v0.1 Feed Me | A real Knuspr cart from a list |
| v0.2 No Surprises | Substitutes, unmapped items, minimum order, delivery slots |
| v0.3 Moving Day | Change country without rebuilding your product list |
| v0.4 It Remembers | Price changes, staples, "you usually buy…" suggestions |
| v0.5 Hands-Free | Siri, schedules, notifications |
| v0.6 Shop Around | More shops, split orders |
| v0.7 Cook Club | Recipes |
| v1.0 For Everyone | Setup without knowing what MCP is |

## Development

```
git clone https://github.com/gabriel-augustus/restockr
claude --plugin-dir ./restockr
uv run --with pytest --with pypdf pytest tests/
```

## License

[MIT](LICENSE)
