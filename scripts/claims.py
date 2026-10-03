"""Report claims (C-xxx): each cites E/O/R; support_level is computed, never typed by hand."""
from __future__ import annotations

import argparse
from pathlib import Path

import ids
import rw_io
import trace

P = rw_io.PATHS


def add_claim(ws, text, cites, section=None) -> dict:
    ws = Path(ws)
    cites = [c.strip() for c in cites if c.strip()]
    if not cites:
        raise ValueError("a claim must cite at least one E/O/R")
    for c in cites:
        prefix = c.split("-")[0]
        if prefix not in ("E", "O", "R") or c not in ids.existing_ids(ws, prefix):
            raise ValueError(f"unknown or invalid citation {c} (claims cite existing E, O or R IDs)")
    if not (text or "").strip():
        raise ValueError("claim text is empty")
    claim = {"id": ids.next_id(ws, "C"), "text": text.strip(), "cites": cites,
             "support_level": trace.compute_support_level(cites), "section": section}
    rw_io.append_jsonl(ws / P["claims"], claim)
    return claim


def render_list(ws, section=None) -> str:
    rows = rw_io.read_jsonl(Path(ws) / P["claims"])
    return "".join(f"[{c['id']}] ({c['support_level']}) {c['text']} — {', '.join(c['cites'])}\n"
                   for c in rows if section is None or c.get("section") == section)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Add or list report claims.")
    ap.add_argument("--workspace")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ad = sub.add_parser("add")
    ad.add_argument("--text", required=True)
    ad.add_argument("--cites", required=True, help="comma-separated E/O/R IDs")
    ad.add_argument("--section")
    ls = sub.add_parser("list")
    ls.add_argument("--section")
    a = ap.parse_args(argv)
    ws = rw_io.resolve_workspace(a.workspace)
    if a.cmd == "add":
        c = add_claim(ws, a.text, a.cites.split(","), a.section)
        print(f"{c['id']} ({c['support_level']})")
    else:
        print(render_list(ws, a.section), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(rw_io.run_cli(main))
