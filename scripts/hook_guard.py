"""PreToolUse hook: keep human-only actions human-only and frozen artifacts frozen (exit 2 blocks).

Stdlib only and Python 3.9 compatible: it must keep working on whatever python3 the wrapper falls back to.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

STATE, LOG, PROTOCOL = "rw/state.json", "rw/decision-log.jsonl", "protocol/protocol.yaml"
RW_STATE = re.compile(r"\brw_state\b")
APPROVE = re.compile(r"\bapprove\b")
WRITE_OP = re.compile(r"(>|\btee\b|\bsed\b[^\n|;&]*\s-i|\bcp\b|\bmv\b|\brm\b|\btruncate\b|\bdd\b|\bopen\(|write_text|"
                      r"write_bytes|\.write\(|\bperl\b[^\n|;&]*\s-i)")
SPEC = re.compile(r"experiments/(X-\d{3,})/spec\.yaml")
ABS_PATH = re.compile(r"(/[^\s'\"]*?)/(?:rw|protocol|experiments)/")
HUMAN_ONLY_MSG = "Gate approval and protocol amendments are human-only. Ask the user to run /rw-approve themselves."


def find_workspace(start: Path) -> Path | None:
    p = Path(start).resolve()
    if not p.is_dir():
        p = p.parent
    for d in (p, *p.parents):
        if (d / STATE).is_file():
            return d
    return None


def _gates(ws: Path) -> dict:
    try:
        return json.loads((ws / STATE).read_text(encoding="utf-8")).get("gates", {})
    except (OSError, ValueError):
        return {}


def frozen_reason(ws: Path, rel: str) -> str | None:
    if rel in (STATE, LOG):
        return f"{rel} is written only by rw_state.py (use the scripts, not direct edits)."
    gates = _gates(ws)
    if rel == PROTOCOL and gates.get("G1", {}).get("approved"):
        return ("protocol/protocol.yaml is frozen after G1. Write the full revised protocol with protocol_version +1 "
                "to protocol/amendments/<date>-<slug>.yaml, then ask the user to run "
                "/rw-approve amend <file> --note <reason>.")
    m = SPEC.fullmatch(rel)
    if m and m.group(1) in gates.get("G3", {}).get("approved_ids", []):
        return (f"{m.group(1)} was approved at G3, so its spec (metrics, split, plan) is frozen. "
                f"Create a new experiment instead and record why.")
    return None


def check_bash(cmd: str, cwd: str | None) -> str | None:
    if RW_STATE.search(cmd) and APPROVE.search(cmd):
        return HUMAN_ONLY_MSG
    if not WRITE_OP.search(cmd):
        return None
    candidates = [Path(cwd or ".")] + [Path(m.group(1)) for m in ABS_PATH.finditer(cmd)]
    workspaces = {ws for ws in (find_workspace(c) for c in candidates) if ws is not None}
    for ws in workspaces:
        for rel in [STATE, LOG, PROTOCOL] + [f"experiments/{x}/spec.yaml" for x in SPEC.findall(cmd)]:
            if rel in cmd:
                reason = frozen_reason(ws, rel)
                if reason:
                    return reason
    if not workspaces and (STATE in cmd or LOG in cmd):
        return f"{STATE} and {LOG} are written only by rw_state.py."
    return None


def check(data) -> str | None:
    tool = data.get("tool_name")
    ti = data.get("tool_input") or {}
    if tool == "Bash":
        return check_bash(ti.get("command") or "", data.get("cwd"))
    if tool not in ("Write", "Edit", "MultiEdit") or not ti.get("file_path"):
        return None
    path = Path(ti["file_path"])
    if not path.is_absolute():
        path = Path(data.get("cwd") or ".") / path
    ws = find_workspace(path)
    if ws is None:
        return None
    try:
        rel = path.resolve().relative_to(ws).as_posix()
    except ValueError:
        return None
    return frozen_reason(ws, rel)


def main(stdin=None) -> int:
    msg = check(json.load(stdin or sys.stdin))
    if msg:
        print(msg, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
