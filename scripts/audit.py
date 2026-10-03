"""Build report/audit.json: automated checks (trace, DOIs, comments) + per-claim reviews."""
from __future__ import annotations

import argparse
from pathlib import Path

import comments
import rw_io
import trace

P = rw_io.PATHS
VERDICTS = ("PASS", "WEAKEN", "MISMATCH", "NOT_FOUND", "HUMAN_REVIEW")
EVIDENCE_STATUSES = ("pending", "verified", "weaken", "rejected", "human-review")


def _issue(code, severity, message, ids=()):
    return {"code": code, "severity": severity, "message": message, "ids": list(ids)}


def _cited_records(g) -> set[str]:
    out = set()
    for c in g["claims"].values():
        for ref in c.get("cites", []):
            ev = g["evidence"].get(ref)
            if ev:
                out.add(ev.get("study_id"))
    return out


def run_automated(ws) -> dict:
    ws = Path(ws)
    existing = rw_io.read_json(ws / P["audit"]) if (ws / P["audit"]).exists() else {}
    rep = trace.trace(ws)
    issues = [_issue("TRACE", "blocking", m) for m in rep.errors]
    issues += [_issue("TRACE_WARN", "warning", m) for m in rep.warnings]
    g = trace.load_graph(ws)
    verified = {v["id"]: v for v in rw_io.read_jsonl(ws / P["doi_verification"])}  # last check wins
    for sid in sorted(_cited_records(g)):
        rec = g["records"].get(sid)
        if rec is None:
            continue
        if not rec.get("doi"):
            issues.append(_issue("NO_DOI", "warning", f"{sid}: no DOI; verify the source manually", [sid]))
        elif sid not in verified:
            issues.append(_issue("DOI_UNVERIFIED", "blocking",
                                 f"{sid}: DOI {rec['doi']} not verified yet (run verify_doi.py)", [sid]))
        elif verified[sid].get("status") != "verified":
            v = verified[sid]
            issues.append(_issue("DOI_" + v["status"].upper().replace("-", "_"), "blocking",
                                 f"{sid}: {v['status']} {v.get('detail') or ''}".strip(), [sid]))
    for kid in comments.summarize(ws)["open_must"]:
        issues.append(_issue("COMMENT_OPEN", "blocking", f"{kid}: must-fix comment is still open", [kid]))
    result = {"generated_at": rw_io.now_iso(), "automated_issues": issues,
              "claim_reviews": existing.get("claim_reviews", [])}
    rw_io.write_json(ws / P["audit"], result)
    return result


def add_review(ws, claim_id, verdict, note=None) -> dict:
    ws = Path(ws)
    if verdict not in VERDICTS:
        raise ValueError(f"verdict must be one of {', '.join(VERDICTS)}")
    if claim_id not in trace.load_graph(ws)["claims"]:
        raise ValueError(f"unknown claim {claim_id}")
    path = ws / P["audit"]
    a = rw_io.read_json(path) if path.exists() else {"generated_at": rw_io.now_iso(),
                                                       "automated_issues": [], "claim_reviews": []}
    review = {"claim_id": claim_id, "verdict": verdict, "note": note, "reviewed_at": rw_io.now_iso()}
    a["claim_reviews"] = [r for r in a.get("claim_reviews", []) if r["claim_id"] != claim_id] + [review]
    rw_io.write_json(path, a)
    return review


def set_evidence_status(ws, evidence_id, status, note=None) -> dict:
    ws = Path(ws)
    if status not in EVIDENCE_STATUSES:
        raise ValueError(f"status must be one of {', '.join(EVIDENCE_STATUSES)}")
    rows = rw_io.read_jsonl(ws / P["evidence"])
    row = next((e for e in rows if e.get("id") == evidence_id), None)
    if row is None:
        raise ValueError(f"unknown evidence {evidence_id}")
    row["verification_status"] = status
    row["verification_note"] = note
    rw_io.write_jsonl(ws / P["evidence"], rows)
    return row


def blocking_issues(ws) -> list[str]:
    ws = Path(ws)
    path = ws / P["audit"]
    if not path.exists():
        return ["report/audit.json is missing (run audit.py run)"]
    a = rw_io.read_json(path)
    out = [f"{i['code']}: {i['message']}" for i in a.get("automated_issues", []) if i.get("severity") == "blocking"]
    reviews = {r["claim_id"]: r for r in a.get("claim_reviews", [])}
    for cid in sorted(trace.load_graph(ws)["claims"]):
        r = reviews.get(cid)
        if r is None:
            out.append(f"{cid}: no claim review yet")
        elif r["verdict"] != "PASS":
            out.append(f"{cid}: verdict {r['verdict']}" + (f" — {r['note']}" if r.get("note") else ""))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Audit a research workspace before release.")
    ap.add_argument("--workspace")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run", parents=[rw_io.ws_parent()], help="run automated checks and write report/audit.json")
    rv = sub.add_parser("review", parents=[rw_io.ws_parent()], help="record a verdict for one claim")
    rv.add_argument("claim_id")
    rv.add_argument("--verdict", required=True, choices=VERDICTS)
    rv.add_argument("--note")
    ev = sub.add_parser("evidence", parents=[rw_io.ws_parent()], help="set verification_status of one evidence record")
    ev.add_argument("evidence_id")
    ev.add_argument("--status", required=True, choices=EVIDENCE_STATUSES)
    ev.add_argument("--note")
    sub.add_parser("status", parents=[rw_io.ws_parent()], help="list blocking issues")
    a = ap.parse_args(argv)
    ws = rw_io.resolve_workspace(a.workspace)
    if a.cmd == "run":
        res = run_automated(ws)
        n = sum(1 for i in res["automated_issues"] if i["severity"] == "blocking")
        print(f"automated issues: {len(res['automated_issues'])} ({n} blocking)")
    elif a.cmd == "review":
        add_review(ws, a.claim_id, a.verdict, a.note)
        print(f"{a.claim_id}: {a.verdict}")
    elif a.cmd == "evidence":
        set_evidence_status(ws, a.evidence_id, a.status, a.note)
        print(f"{a.evidence_id}: {a.status}")
    blocking = blocking_issues(ws)
    for b in blocking:
        print(f"BLOCKING {b}")
    if a.cmd == "status":
        print("OK: no blocking issues" if not blocking else f"FAIL: {len(blocking)} blocking issue(s)")
        return 1 if blocking else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(rw_io.run_cli(main))
