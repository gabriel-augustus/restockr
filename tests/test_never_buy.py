"""Tests run the hook exactly as Claude Code does: the command from hooks.json, through
a shell, with whatever `python3` is on PATH (on macOS: the system Python 3.9).
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMAND = json.loads((ROOT / "hooks/hooks.json").read_text())["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
P = "mcp__plugin_restockr_knuspr__"


def run(stdin: str, plugin_root: Path = ROOT) -> subprocess.CompletedProcess:
    env = {**os.environ, "CLAUDE_PLUGIN_ROOT": str(plugin_root)}
    return subprocess.run(["sh", "-c", COMMAND], input=stdin, capture_output=True, text=True, env=env)


def denied(tool: str) -> bool:
    r = run(json.dumps({"tool_name": tool, "tool_input": {}}))
    if r.returncode == 2:
        return True
    assert r.returncode == 0, r.stderr
    return bool(r.stdout.strip()) and \
        json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_runs_cleanly_on_system_python():
    r = run(json.dumps({"tool_name": P + "get_cart"}))
    assert (r.returncode, r.stderr, r.stdout) == (0, "", ""), f"{shutil.which('python3')}: {r.stderr}"


def test_blocks_checkout_payment_and_order_changes():
    for t in ["update_payment_method_checkout", "reserve_timeslot", "change_timeslot_checkout",
              "select_delivery_address_checkout", "set_checkout_as_suborder", "repeat_order",
              "cancel_order", "remove_order_items", "create_scheduled_task", "submit_claim",
              "submit_credit_compensation", "credit_customer_returnables", "delete_shopping_list"]:
        assert denied(P + t), t


def test_blocks_unknown_future_tools():
    assert denied(P + "place_order")
    assert denied(P + "some_tool_knuspr_adds_next_year")


def test_allows_reading_and_the_cart():
    for t in ["batch_search_products", "get_product_details", "get_cart", "get_checkout_link",
              "fetch_orders", "add_items_to_cart", "update_cart_item", "remove_cart_item",
              "clear_cart"]:
        assert not denied(P + t), t


def test_fails_closed_on_garbage():
    r = run("not json")
    assert r.returncode == 0
    assert json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_fails_closed_when_the_script_crashes(tmp_path):
    (tmp_path / "hooks").mkdir()
    (tmp_path / "hooks/never_buy.py").write_text("raise SystemExit('boom')\n")
    r = run(json.dumps({"tool_name": P + "cancel_order"}), plugin_root=tmp_path)
    assert r.returncode == 2 and "denied" in r.stderr


def test_fails_closed_when_the_script_is_missing(tmp_path):
    r = run(json.dumps({"tool_name": P + "cancel_order"}), plugin_root=tmp_path)
    assert r.returncode == 2
