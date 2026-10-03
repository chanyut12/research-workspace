"""Hand out the next free ID for each prefix so agents never invent IDs themselves."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import rw_io

PREFIXES = ("RQ", "Q", "S", "E", "M", "O", "K", "H", "X", "R", "C")
_NUM = re.compile(r"^([A-Z]+)-(\d+)")
P = rw_io.PATHS


def _ids(rows, key="id") -> list[str]:
    return [r[key] for r in rows if isinstance(r, dict) and r.get(key)]


def existing_ids(ws, prefix: str) -> set[str]:
    ws = Path(ws)
    if prefix == "RQ":
        return set(_ids((rw_io.read_yaml(ws / P["protocol"]) or {}).get("research_questions") or []))
    if prefix == "Q":
        return set(_ids(rw_io.read_csv(ws / P["search_log"]), "query_id"))
    if prefix == "M":
        return set(_ids([rw_io.read_yaml(p) for p in ws.glob("meetings/*/meeting.yaml")]))
    if prefix == "H":
        return set(_ids((rw_io.read_yaml(ws / P["hypotheses"]) or {}).get("hypotheses") or []))
    if prefix == "X":
        return {p.name for p in ws.glob("experiments/X-*") if p.is_dir()}
    if prefix == "R":
        found = set()
        for p in ws.glob("experiments/*/results.jsonl"):
            found |= set(_ids(rw_io.read_jsonl(p)))
        return found
    files = {"S": "records", "E": "evidence", "O": "observations", "K": "comments", "C": "claims"}
    if prefix in files:
        return set(_ids(rw_io.read_jsonl(ws / P[files[prefix]])))
    raise ValueError(f"unknown ID prefix {prefix!r}; one of {', '.join(PREFIXES)}")


def max_num(id_list) -> int:
    return max((int(m.group(2)) for i in id_list if (m := _NUM.match(i))), default=0)


def next_id(ws, prefix: str) -> str:
    n = max_num(existing_ids(ws, prefix)) + 1
    return f"RQ-{n}" if prefix == "RQ" else f"{prefix}-{n:03d}"


def next_run_id(ws, x_id: str) -> str:
    runs = rw_io.read_jsonl(Path(ws) / "experiments" / x_id / "runs.jsonl")
    return f"RUN-{max_num(_ids(runs, 'run_id')) + 1:03d}"


def all_ids(ws) -> set[str]:
    out = set()
    for prefix in PREFIXES:
        out |= existing_ids(ws, prefix)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Print the next free ID for a prefix.")
    ap.add_argument("command", choices=["next"])
    ap.add_argument("prefix", choices=PREFIXES)
    ap.add_argument("--workspace")
    a = ap.parse_args(argv)
    print(next_id(rw_io.resolve_workspace(a.workspace), a.prefix))
    return 0


if __name__ == "__main__":
    raise SystemExit(rw_io.run_cli(main))
