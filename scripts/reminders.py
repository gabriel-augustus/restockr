# /// script
# requires-python = ">=3.10"
# ///
"""Read the grocery list from Apple Reminders (macOS only, read-only).

Usage:
  uv run reminders.py lists
      Names of all Reminders lists, as JSON.
  uv run reminders.py use "<list name>"
      Remember which list is the grocery list (~/Restockr/config.json).
  uv run reminders.py items [--list "<list name>"]
      Open (not completed) items of the grocery list, as JSON:
      [{"name": "milk", "notes": ""}, ...]

The first run makes macOS ask whether this app may access Reminders.
Nothing is ever changed in Reminders.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import store  # noqa: E402

JXA_LISTS = 'JSON.stringify(Application("Reminders").lists.name())'
JXA_ITEMS = """
function run(argv) {
  const R = Application("Reminders");
  const matches = R.lists.whose({name: argv[0]})();
  if (matches.length === 0) return JSON.stringify({error: "no list named " + argv[0]});
  const open = matches[0].reminders.whose({completed: false})();
  return JSON.stringify(open.map(r => ({name: r.name(), notes: r.body() || ""})));
}
"""


def _osascript(script: str, *args: str) -> str:
    r = subprocess.run(["osascript", "-l", "JavaScript", "-e", script, *args],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"Reminders not readable: {r.stderr.strip()}\n"
                         "Allow access in System Settings > Privacy & Security > Reminders "
                         "(and Automation), then try again.")
    return r.stdout.strip()


def clean_items(raw: list[dict]) -> list[dict]:
    """Trim names, drop empty ones."""
    out = []
    for r in raw:
        name = " ".join(str(r.get("name") or "").split())
        if name:
            out.append({"name": name, "notes": " ".join(str(r.get("notes") or "").split())})
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("lists")
    s = sub.add_parser("use"); s.add_argument("name")
    s = sub.add_parser("items"); s.add_argument("--list")
    a = ap.parse_args(argv[1:])
    if a.cmd == "lists":
        print(_osascript(JXA_LISTS))
        return 0
    if a.cmd == "use":
        names = json.loads(_osascript(JXA_LISTS))
        if a.name not in names:
            print(f"No list {a.name!r}. Lists: {names}")
            return 1
        cfg = store.load_config()
        cfg["reminders_list"] = a.name
        store.save_config(cfg)
        print(f"grocery list = {a.name!r}")
        return 0
    name = a.list or store.load_config().get("reminders_list")
    if not name:
        print("NO_LIST_CONFIGURED: run `reminders.py lists`, ask the user which one, then `reminders.py use`")
        return 2
    result = json.loads(_osascript(JXA_ITEMS, name))
    if isinstance(result, dict):
        print(result["error"])
        return 1
    print(json.dumps(clean_items(result), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
