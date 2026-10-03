"""PreToolUse hook: keep human-only actions human-only and frozen artifacts frozen (exit 2 blocks)."""
import json
import re
import sys
from pathlib import Path

HUMAN_ONLY = re.compile(r"rw_state\.py[\"']?\s+(--workspace\s+\S+\s+)?approve\b")
SPEC = re.compile(r"experiments/(X-\d{3,})/spec\.yaml")


def check(data) -> str | None:
    tool = data.get("tool_name")
    ti = data.get("tool_input") or {}
    if tool == "Bash":
        if HUMAN_ONLY.search(ti.get("command") or ""):
            return ("Gate approval and protocol amendments are human-only. "
                    "Ask the user to run /rw-approve themselves.")
        return None
    if tool not in ("Write", "Edit", "MultiEdit") or not ti.get("file_path"):
        return None
    try:
        import rw_io
    except ImportError:
        return None
    path = Path(ti["file_path"])
    if not path.is_absolute():
        path = Path(data.get("cwd") or ".") / path
    ws = rw_io.find_workspace(path)
    if ws is None:
        return None
    try:
        rel = path.resolve().relative_to(ws).as_posix()
    except ValueError:
        return None
    if rel in (rw_io.PATHS["state"], rw_io.PATHS["decision_log"]):
        return f"{rel} is written only by rw_state.py (use the scripts, not direct edits)."
    gates = rw_io.read_json(ws / rw_io.PATHS["state"]).get("gates", {})
    if rel == rw_io.PATHS["protocol"] and gates.get("G1", {}).get("approved"):
        return ("protocol/protocol.yaml is frozen after G1. Write the full revised protocol with protocol_version +1 "
                "to protocol/amendments/<date>-<slug>.yaml, then ask the user to run "
                "/rw-approve amend <file> --note <reason>.")
    m = SPEC.fullmatch(rel)
    if m and m.group(1) in gates.get("G3", {}).get("approved_ids", []):
        return (f"{m.group(1)} was approved at G3, so its spec (metrics, split, plan) is frozen. "
                f"Create a new experiment instead and record why.")
    return None


def main(stdin=None) -> int:
    msg = check(json.load(stdin or sys.stdin))
    if msg:
        print(msg, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
