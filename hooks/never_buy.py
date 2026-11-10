#!/usr/bin/env python3
"""PreToolUse hook: Restockr never places, confirms or pays for an order.

Runs before every Knuspr MCP tool call (see hooks/hooks.json). ALLOWLIST: only
read-only tools and the cart tools may run. Everything else is denied, including
tools Knuspr adds in the future, until someone reviews them and adds them here.
Fails closed: if the hook input can't be read, the call is denied.

Reviewed against Knuspr's tool list on 2026-11-10 (58 tools).

Must run on old system Pythons (macOS ships 3.9): stdlib only, no 3.10+ syntax.
hooks.json also turns any crash of this script into a deny (exit code 2).
"""
from __future__ import annotations

import json
import sys

# Read-only: products, cart, past orders, account info, help content.
ALLOW_READ = {
    "batch_search_products", "get_product_details", "get_products_composition_batch",
    "get_discounted_items", "get_all_user_favorites", "get_typical_order",
    "fetch_orders", "analyze_spending",
    "get_cart", "get_checkout", "get_checkout_link", "get_timeslots_checkout",
    "get_user_info", "get_user_addresses", "search_address",
    "get_user_shopping_lists_preview", "get_user_shopping_list_detail",
    "get_user_scheduled_tasks", "get_user_reusable_bags_info", "get_bag_delivery_history",
    "get_customer_returnables", "get_customer_returnables_declaration",
    "get_announcements", "get_faq_content", "get_customer_support_contact_info",
    "get_recipe_detail", "search_recipes_by_vector_similarity", "get_url_content",
}
# The cart is Restockr's whole job: build it, then hand it to the user.
ALLOW_CART = {"add_items_to_cart", "update_cart_item", "remove_cart_item", "clear_cart"}
ALLOWED = ALLOW_READ | ALLOW_CART

# Denied on purpose (anything not allowed is denied anyway; this list documents why):
#   checkout & payment: update_payment_method_checkout, change_timeslot_checkout,
#     reserve_timeslot, unreserve_timeslot, select_delivery_address_checkout,
#     change_checkout_packaging, toggle_delivery_note_checkout,
#     update_courier_instructions_checkout, set_checkout_as_suborder
#   existing orders: repeat_order, cancel_order, remove_order_items, update_order_courier_note
#   automation: create_scheduled_task, cancel_scheduled_task
#   money & claims: submit_claim, submit_credit_compensation, credit_customer_returnables
#   account & other writes: adjust_user_reusable_bags, add_karma_rating, submit_product_wish,
#     request_delivery_expansion, create_shopping_list, delete_shopping_list,
#     add_products_to_shopping_list, remove_products_from_shopping_list


def decide(tool_name: str) -> str | None:
    tool = tool_name.split("__")[-1]  # mcp__plugin_restockr_knuspr__<tool>
    if tool in ALLOWED:
        return None
    return (f"Restockr only reads from Knuspr and edits the cart; '{tool}' is not allowed. "
            "Checkout, payment, delivery slots and existing orders stay with the user, "
            "in the Knuspr app.")


def main() -> int:
    try:
        tool_name = json.load(sys.stdin)["tool_name"]
    except Exception:
        reason = "Restockr never-buy hook could not read the tool call; denied to be safe."
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
