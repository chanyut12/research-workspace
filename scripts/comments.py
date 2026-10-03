"""Track advisor/expert comments (K-xxx): summary, resolution and a markdown table."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import ids
import rw_io

STATUSES = ("open", "addressed", "declined", "deferred")
P = rw_io.PATHS


def load_comments(ws) -> list[dict]:
    return rw_io.read_jsonl(Path(ws) / P["comments"])


def summarize(ws) -> dict:
    cs = load_comments(ws)
    by_status = {s: 0 for s in STATUSES}
    for c in cs:
        by_status[c.get("status", "open")] = by_status.get(c.get("status", "open"), 0) + 1
    open_ = [c for c in cs if c.get("status") == "open"]
    return {"total": len(cs), "by_status": by_status, "open": [c["id"] for c in open_],
            "open_must": [c["id"] for c in open_ if c.get("severity") == "must"]}


def resolve(ws, comment_id, status, resolution=None, changed_ids=None, deferred_until=None) -> dict:
    ws = Path(ws)
    if status not in STATUSES:
        raise ValueError(f"status must be one of {', '.join(STATUSES)}")
    cs = load_comments(ws)
    target = next((c for c in cs if c.get("id") == comment_id), None)
    if target is None:
        raise ValueError(f"unknown comment {comment_id}")
    changed_ids = list(changed_ids or [])
    if status == "addressed" and not changed_ids:
        raise ValueError("addressed requires --changed <IDs of the artifacts that changed>")
    if status == "declined" and not (resolution or "").strip():
        raise ValueError("declined requires --resolution <reason>")
    if status == "deferred" and not deferred_until:
        raise ValueError("deferred requires --until <when>")
    unknown = [i for i in changed_ids if i not in ids.all_ids(ws)]
    if unknown:
        raise ValueError(f"unknown IDs in --changed: {', '.join(unknown)}")
    target.update(status=status, resolution=resolution, changed_ids=changed_ids,
                  deferred_until=deferred_until, updated_at=rw_io.now_iso())
    rw_io.write_jsonl(ws / P["comments"], cs)
    rw_io.append_jsonl(ws / P["decision_log"], {
        "timestamp": rw_io.now_iso(), "kind": "note", "from": None, "to": None, "gate": None,
        "ids": [comment_id, *changed_ids], "reason": f"comment {comment_id} -> {status}: {resolution or ''}".strip(),
        "cause_ids": [comment_id]})
    return target


def _cell(v) -> str:
    return str(v if v is not None else "").replace("|", "\\|").replace("\n", " ")


def render_markdown(comments: list[dict]) -> str:
    if not comments:
        return "_ไม่มี comments_\n"
    lines = ["| ID | Meeting | Target | Severity | Status | Comment | Resolution |",
             "|---|---|---|---|---|---|---|"]
    for c in comments:
        how = c.get("resolution") or ""
        if c.get("changed_ids"):
            how += f" (changed: {', '.join(c['changed_ids'])})"
        if c.get("deferred_until"):
            how += f" (until {c['deferred_until']})"
        lines.append("| " + " | ".join(_cell(x) for x in (c["id"], c["meeting_id"], c["target"], c["severity"],
                                                          c["status"], c["text"], how.strip())) + " |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Summarize or resolve meeting comments (K-xxx).")
    ap.add_argument("--workspace")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("summary")
    s.add_argument("--json", action="store_true")
    sub.add_parser("table")
    r = sub.add_parser("resolve")
    r.add_argument("comment_id")
    r.add_argument("--status", required=True, choices=STATUSES)
    r.add_argument("--resolution")
    r.add_argument("--changed", default="", help="comma-separated IDs that changed")
    r.add_argument("--until")
    a = ap.parse_args(argv)
    ws = rw_io.resolve_workspace(a.workspace)
    if a.cmd == "summary":
        s = summarize(ws)
        if a.json:
            print(json.dumps(s, ensure_ascii=False, indent=2))
        else:
            print(f"comments: {s['total']} · " + ", ".join(f"{k}={v}" for k, v in s["by_status"].items()))
            print(f"open: {', '.join(s['open']) or '-'} · open must: {', '.join(s['open_must']) or '-'}")
    elif a.cmd == "table":
        print(render_markdown(load_comments(ws)), end="")
    else:
        changed = [x.strip() for x in a.changed.split(",") if x.strip()]
        c = resolve(ws, a.comment_id, a.status, a.resolution, changed, a.until)
        print(f"{c['id']} -> {c['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(rw_io.run_cli(main))
