#!/usr/bin/env python3
"""PreToolUse hook: Restockr never places, confirms or pays for an order.

Runs before every shop MCP tool call (see hooks/hooks.json). Denies any tool whose
name looks like checkout/ordering/payment. Fails closed: if the hook input can't be
read, the call is denied.

Explicit names go in DENY_EXACT once we know a shop's real tool list. Patterns stay
as a safety net for tools a shop adds later.
"""
import json
import re
import sys

DENY_EXACT: set[str] = set()  # filled in after listing Knuspr's tools
DENY_PATTERN = re.compile(
    r"checkout|pay(ment)?|purchase|place|submit|confirm|finali[sz]e|"
    r"(create|make|send|complete)_?order|order_?(create|submit|send|now)|buy",
    re.IGNORECASE,
)


def decide(tool_name: str) -> str | None:
    tool = tool_name.split("__")[-1]  # mcp__<server>__<tool>
    if tool in DENY_EXACT or DENY_PATTERN.search(tool):
        return (f"Restockr never places, confirms or pays for orders ('{tool}' blocked). "
                "Build the cart, then let the user check out in the shop app.")
    return None


def main() -> int:
    try:
        tool_name = json.load(sys.stdin)["tool_name"]
    except Exception:
        tool_name, reason = "?", "Restockr never-buy hook could not read the tool call; denied to be safe."
    else:
        reason = decide(tool_name)
    if reason:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
