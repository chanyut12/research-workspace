"""Record the conclusion (verdict) of a tested hypothesis: supported / refuted / inconclusive."""
from __future__ import annotations

import argparse
from pathlib import Path

import rw_io
import trace

P = rw_io.PATHS


def record_verdict(ws, hid, outcome, result_ids, compared_with, rationale) -> dict:
    """Call only after the user agreed with the interpretation."""
    ws = Path(ws)
    if outcome not in trace.OUTCOMES:
        raise ValueError(f"outcome must be one of {', '.join(trace.OUTCOMES)}")
    if not (rationale or "").strip():
        raise ValueError("a verdict needs --rationale (why the results support, refute or leave it open)")
    result_ids, compared_with = list(result_ids or []), list(compared_with or [])
    if not result_ids:
        raise ValueError("a verdict needs at least one --results R-…")
    with rw_io.workspace_lock(ws):
        g = trace.load_graph(ws)
        h = g["hypotheses"].get(hid)
        if h is None:
            raise ValueError(f"unknown hypothesis {hid}")
        if h.get("status") not in ("approved", "tested"):
            raise ValueError(f"{hid} has status {h.get('status')}; only approved hypotheses can be concluded")
        explo, mine = trace.exploratory_results(g), trace.confirmatory_results_for(g, hid)
        for rid in result_ids:
            if rid not in g["results"]:
                raise ValueError(f"unknown result {rid}")
            if rid in explo:
                raise ValueError(f"{rid} is exploratory; a hypothesis is tested only by confirmatory results")
            if rid not in mine:
                raise ValueError(f"{rid} is not a result of an experiment testing {hid}")
        for ref in compared_with:
            if ref.split("-")[0] not in ("E", "O") or not trace.exists(g, ref):
                raise ValueError(f"--compare takes existing E/O IDs; {ref} is not one")
        data = rw_io.read_yaml(ws / P["hypotheses"])
        target = next(x for x in data["hypotheses"] if x["id"] == hid)
        target["status"] = "tested"
        target["verdict"] = {"outcome": outcome, "result_ids": result_ids, "compared_with": compared_with,
                             "rationale": rationale.strip(), "decided_at": rw_io.now_iso()}
        rw_io.write_yaml(ws / P["hypotheses"], data)
        rw_io.append_jsonl(ws / P["decision_log"], {
            "timestamp": rw_io.now_iso(), "kind": "note", "from": None, "to": None, "gate": None,
            "ids": [hid, *result_ids, *compared_with], "reason": f"verdict {hid}: {outcome} — {rationale.strip()}",
            "cause_ids": []})
        return target


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Conclude a tested hypothesis.")
    ap.add_argument("--workspace")
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("verdict", parents=[rw_io.ws_parent()])
    v.add_argument("hypothesis_id")
    v.add_argument("--outcome", required=True, choices=trace.OUTCOMES)
    v.add_argument("--results", required=True, help="comma-separated confirmatory R-IDs")
    v.add_argument("--compare", default="", help="comma-separated E/O IDs the result is compared with")
    v.add_argument("--rationale", required=True)
    a = ap.parse_args(argv)
    split = lambda s: [x.strip() for x in s.split(",") if x.strip()]
    h = record_verdict(rw_io.resolve_workspace(a.workspace), a.hypothesis_id, a.outcome, split(a.results),
                       split(a.compare), a.rationale)
    print(f"{h['id']}: {h['verdict']['outcome']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(rw_io.run_cli(main))
