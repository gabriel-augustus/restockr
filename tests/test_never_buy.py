import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "hooks/never_buy.py"


def run(stdin: str) -> dict | None:
    out = subprocess.run([sys.executable, str(HOOK)], input=stdin, capture_output=True, text=True).stdout
    return json.loads(out) if out.strip() else None


def denied(tool: str) -> bool:
    r = run(json.dumps({"tool_name": tool, "tool_input": {}}))
    return bool(r) and r["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_blocks_ordering_tools():
    for t in ["checkout", "place_order", "submitOrder", "confirm_cart", "create_order",
              "pay", "buy_now", "finalize_purchase"]:
        assert denied(f"mcp__plugin_restockr_knuspr__{t}"), t


def test_allows_cart_and_search_tools():
    for t in ["search_products", "add_to_cart", "get_cart", "clear_cart", "get_order_history",
              "remove_from_cart"]:
        assert not denied(f"mcp__plugin_restockr_knuspr__{t}"), t


def test_fails_closed_on_garbage():
    assert run("not json")["hookSpecificOutput"]["permissionDecision"] == "deny"
