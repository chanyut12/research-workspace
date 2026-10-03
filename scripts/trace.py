"""Check the evidence chain S → E / O / R → H → X → R → C and report gaps (spec section 5)."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import rw_io

P = rw_io.PATHS
KIND = {"E": "literature", "O": "expert-opinion", "R": "experimental"}
OUTCOMES = ("supported", "refuted", "inconclusive")
CLAIM_REF = re.compile(r"\[(C-\d{3,})\]")
TABLE = {"RQ": "rq", "Q": "search_log", "S": "records", "E": "evidence", "M": "meetings",
         "O": "observations", "K": "comments", "H": "hypotheses", "X": "experiments", "R": "results", "C": "claims"}


@dataclass
class TraceReport:
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors


def compute_support_level(cites, exploratory_r=frozenset()) -> str:
    kinds = {"exploratory" if c in exploratory_r else KIND[c.split("-")[0]] for c in cites if c.split("-")[0] in KIND}
    return kinds.pop() if len(kinds) == 1 else "mixed"


def exploratory_results(g) -> set[str]:
    return {rid for rid, r in g["results"].items()
            if g["experiments"].get(r.get("experiment_id"), {}).get("kind") == "exploratory"}


def confirmatory_results_for(g, hid) -> list[str]:
    return sorted(rid for rid, r in g["results"].items()
                  if (x := g["experiments"].get(r.get("experiment_id"), {})).get("kind") != "exploratory"
                  and x.get("hypothesis_id") == hid)


def check_verdicts(g) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    explo = exploratory_results(g)
    for hid, h in g["hypotheses"].items():
        v = h.get("verdict")
        if h.get("status") == "tested" and not v:
            errors.append(f"{hid}: status tested but no verdict (record one with hypotheses.py verdict)")
        if not v and h.get("status") == "approved" and confirmatory_results_for(g, hid):
            warnings.append(f"{hid}: has results but no verdict yet")
        if not v:
            continue
        for rid in v.get("result_ids", []):
            if rid not in g["results"]:
                errors.append(f"{hid}: verdict cites missing result {rid}")
            elif rid in explo:
                errors.append(f"{hid}: verdict cites exploratory result {rid}; only confirmatory results can test it")
            elif rid not in confirmatory_results_for(g, hid):
                errors.append(f"{hid}: verdict cites {rid}, which is not from an experiment testing {hid}")
        for ref in v.get("compared_with", []):
            if not exists(g, ref):
                errors.append(f"{hid}: verdict compares with missing {ref}")
    return errors, warnings


def frozen_digest(ws, rel) -> str | None:
    """Digest of a frozen artifact. Specs ignore `status`, which scripts update after G3."""
    path = Path(ws) / rel
    if not path.exists():
        return None
    if rel.endswith("spec.yaml"):
        spec = {k: v for k, v in (rw_io.read_yaml(path) or {}).items() if k != "status"}
        data = json.dumps(spec, sort_keys=True, ensure_ascii=False).encode("utf-8")
    else:
        data = path.read_bytes()
    return hashlib.sha256(data).hexdigest()


def _by_id(rows, key="id") -> dict:
    return {r[key]: r for r in rows if isinstance(r, dict) and r.get(key)}


def load_graph(ws) -> dict:
    ws = Path(ws)
    proto = rw_io.read_yaml(ws / P["protocol"]) or {}
    meetings = {}
    for p in sorted(ws.glob("meetings/*/meeting.yaml")):
        m = rw_io.read_yaml(p) or {}
        if m.get("id"):
            meetings[m["id"]] = m
    experiments, runs, results = {}, {}, {}
    for d in sorted(ws.glob("experiments/X-*")):
        if d.is_dir():
            experiments[d.name] = rw_io.read_yaml(d / "spec.yaml") or {}
            runs[d.name] = _by_id(rw_io.read_jsonl(d / "runs.jsonl"), "run_id")
            results.update(_by_id(rw_io.read_jsonl(d / "results.jsonl")))
    screening = {}  # latest decision per study; full-text outranks title-abstract
    for row in rw_io.read_csv(ws / P["screening"]):
        prev = screening.get(row.get("id"))
        if prev is None or row.get("stage") == "full-text" or prev.get("stage") != "full-text":
            screening[row.get("id")] = row
    report = ws / P["report"]
    state_path = ws / P["state"]
    return {
        "state": rw_io.read_json(state_path) if state_path.exists() else {},
        "rq": _by_id(proto.get("research_questions") or []),
        "search_log": _by_id(rw_io.read_csv(ws / P["search_log"]), "query_id"),
        "records": _by_id(rw_io.read_jsonl(ws / P["records"])),
        "screening": screening,
        "evidence": _by_id(rw_io.read_jsonl(ws / P["evidence"])),
        "meetings": meetings,
        "observations": _by_id(rw_io.read_jsonl(ws / P["observations"])),
        "comments": _by_id(rw_io.read_jsonl(ws / P["comments"])),
        "hypotheses": _by_id((rw_io.read_yaml(ws / P["hypotheses"]) or {}).get("hypotheses") or []),
        "experiments": experiments, "runs": runs, "results": results,
        "claims": _by_id(rw_io.read_jsonl(ws / P["claims"])),
        "report_claim_refs": CLAIM_REF.findall(report.read_text(encoding="utf-8")) if report.exists() else [],
    }


def exists(g, ref) -> bool:
    table = TABLE.get(str(ref).split("-")[0])
    return table is not None and ref in g[table]


def check_hypotheses(g, ids=None) -> list[str]:
    """Rules for hypotheses that are (or are about to be) approved: sources + literature checks."""
    hyps = g["hypotheses"]
    targets = ids if ids is not None else [h for h, v in hyps.items() if v.get("status") in ("approved", "tested")]
    errors = []
    for hid in targets:
        h = hyps.get(hid)
        if h is None:
            errors.append(f"{hid}: hypothesis does not exist")
            continue
        if not h.get("based_on"):
            errors.append(f"{hid}: must cite at least one E/O/R in based_on")
        for ref in h.get("based_on") or []:
            if not exists(g, ref):
                errors.append(f"{hid}: based_on {ref} does not exist")
            elif ref.startswith("O-") and not g["observations"][ref].get("confirmed_by_user"):
                errors.append(f"{hid}: based_on {ref} is not confirmed by the user")
            elif ref.startswith("E-") and g["evidence"][ref].get("verification_status") == "rejected":
                errors.append(f"{hid}: based_on {ref} is rejected evidence")
        checks = h.get("literature_checks") or []
        if not checks:
            errors.append(f"{hid}: no literature_checks (search for supporting and contradicting work first)")
            continue
        missing = [q for q in checks if q not in g["search_log"]]
        if missing:
            errors.append(f"{hid}: literature_checks not in search-log: {', '.join(missing)}")
        purposes = {g["search_log"][q].get("purpose") for q in checks
                    if q in g["search_log"] and g["search_log"][q].get("status") == "ok"}
        contra = bool(purposes & {"contradicting", "both"})
        support = bool(purposes & {"supporting", "both"})
        if h.get("origin") == "literature":
            if not contra:
                errors.append(f"{hid}: origin=literature needs a successful search with purpose contradicting or both")
        elif not (contra and support):
            errors.append(f"{hid}: origin={h.get('origin')} needs successful literature checks covering "
                          f"supporting and contradicting work")
    return errors


def trace(ws) -> TraceReport:
    g = load_graph(ws)
    r = TraceReport()
    E, W = r.errors, r.warnings

    def need(owner, ref):
        if ref and not exists(g, ref):
            E.append(f"{owner}: dangling reference {ref}")

    for rel, digest in sorted((g["state"].get("frozen") or {}).items()):
        if frozen_digest(ws, rel) != digest:
            E.append(f"{rel} changed after approval (frozen at its gate); restore it or use an amendment / new experiment")
    for sid, s in g["records"].items():
        for q in s.get("query_ids", []):
            need(sid, q)
    cited = set()
    for h in g["hypotheses"].values():
        cited |= set(h.get("based_on", []))
    for c in g["claims"].values():
        cited |= set(c.get("cites", []))
    for eid, e in g["evidence"].items():
        sid = e.get("study_id")
        need(eid, sid)
        need(eid, e.get("rq_id"))
        scr = g["screening"].get(sid)
        if sid in g["records"] and (scr is None or scr.get("decision") != "include"):
            E.append(f"{eid}: study {sid} is not screened as include")
        if eid in cited and e.get("verification_status") == "rejected":
            E.append(f"{eid}: rejected evidence is still cited")
    for oid, o in g["observations"].items():
        need(oid, o.get("meeting_id"))
        if not o.get("confirmed_by_user"):
            E.append(f"{oid}: not confirmed by user")
    for kid, k in g["comments"].items():
        need(kid, k.get("meeting_id"))
        if k.get("target") != "general":
            need(kid, k.get("target"))
        for ref in k.get("changed_ids", []):
            need(kid, ref)
    for hid, h in g["hypotheses"].items():
        need(hid, h.get("rq_id"))
        for ref in h.get("based_on", []):
            need(hid, ref)
    E.extend(check_hypotheses(g))
    proposed = [hid for hid, h in g["hypotheses"].items() if h.get("status") == "proposed"]
    W.extend(f"{m} (proposed)" for m in check_hypotheses(g, proposed))
    approved_x = set(g["state"].get("gates", {}).get("G3", {}).get("approved_ids", []))
    explo_r = exploratory_results(g)
    for xid, x in g["experiments"].items():
        need(xid, x.get("hypothesis_id"))
        if x.get("kind") == "exploratory":
            continue
        if g["runs"].get(xid) and xid not in approved_x:
            E.append(f"{xid}: has runs but was never approved at G3")
        h = g["hypotheses"].get(x.get("hypothesis_id"), {})
        for ref in h.get("based_on", []):
            src = g["experiments"].get(g["results"].get(ref, {}).get("experiment_id"), {})
            if ref in explo_r and src.get("dataset") == x.get("dataset"):
                W.append(f"{xid}: tests {x.get('hypothesis_id')} on the same data ({x['dataset'].get('name')} "
                         f"{x['dataset'].get('version')}) that generated it in {src.get('id')}; "
                         f"use held-out or new data")
    for rid, res in g["results"].items():
        xid = res.get("experiment_id")
        if xid not in g["experiments"]:
            E.append(f"{rid}: dangling reference {xid}")
            continue
        run = g["runs"][xid].get(res.get("run_id"))
        if run is None:
            E.append(f"{rid}: dangling reference {res.get('run_id')} in {xid}")
        elif run.get("status") != "ok":
            E.append(f"{rid}: comes from {res.get('run_id')} whose status is {run.get('status')}")
    for cid, c in g["claims"].items():
        for ref in c.get("cites", []):
            need(cid, ref)
        cites = c.get("cites", [])
        expected = compute_support_level(cites, explo_r)
        if expected == "mixed" and any(ref in explo_r for ref in cites):
            E.append(f"{cid}: mixes exploratory results with other evidence; split it into separate claims")
        elif c.get("support_level") != expected:
            E.append(f"{cid}: support_level is {c.get('support_level')} but its citations imply {expected}")
    for ref in sorted(set(g["report_claim_refs"])):
        if ref not in g["claims"]:
            E.append(f"report.md: [{ref}] is not in claims.jsonl")
    if g["report_claim_refs"]:
        unused = sorted(set(g["claims"]) - set(g["report_claim_refs"]))
        if unused:
            W.append(f"claims not used in report.md: {', '.join(unused)}")

    v_errors, v_warnings = check_verdicts(g)
    E.extend(v_errors)
    W.extend(v_warnings)
    tested = {x.get("hypothesis_id") for x in g["experiments"].values()}
    untested = sorted(h for h, v in g["hypotheses"].items() if v.get("status") == "approved" and h not in tested)
    W.extend(f"{h}: approved but no experiment yet" for h in untested)
    used_o = {x for h in g["hypotheses"].values() for x in h.get("based_on", []) if x.startswith("O-")}
    used_o |= {x for c in g["claims"].values() for x in c.get("cites", []) if x.startswith("O-")}
    r.summary = {
        "hypotheses_by_origin": dict(Counter(h.get("origin") for h in g["hypotheses"].values())),
        "untested_hypotheses": untested,
        "unused_observations": sorted(set(g["observations"]) - used_o),
        "open_comments": sorted(k for k, v in g["comments"].items() if v.get("status") == "open"),
        "verdicts": {h: v["verdict"]["outcome"] for h, v in sorted(g["hypotheses"].items()) if v.get("verdict")},
        "counts": {k: len(g[k]) for k in ("records", "evidence", "observations", "comments",
                                          "hypotheses", "experiments", "results", "claims")},
    }
    return r


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Check the evidence chain of a research workspace.")
    ap.add_argument("--workspace")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    r = trace(rw_io.resolve_workspace(a.workspace))
    if a.json:
        print(json.dumps({"ok": r.ok, "errors": r.errors, "warnings": r.warnings, "summary": r.summary},
                         ensure_ascii=False, indent=2))
    else:
        for e in r.errors:
            print(f"ERROR {e}")
        for w in r.warnings:
            print(f"WARN  {w}")
        s = r.summary
        print("counts: " + ", ".join(f"{k}={v}" for k, v in s["counts"].items()))
        print(f"hypotheses by origin: {s['hypotheses_by_origin'] or '-'}")
        print(f"untested hypotheses: {', '.join(s['untested_hypotheses']) or '-'}")
        print(f"unused observations: {', '.join(s['unused_observations']) or '-'}")
        print(f"open comments: {', '.join(s['open_comments']) or '-'}")
        print("verdicts: " + (", ".join(f"{h}={o}" for h, o in s["verdicts"].items()) or "-"))
        print("OK: evidence chain intact" if r.ok else f"FAIL: {len(r.errors)} error(s)")
    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(rw_io.run_cli(main))
