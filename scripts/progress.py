"""Build progress/<date>-review.md for an advisor meeting, straight from the artifacts."""
from __future__ import annotations

import argparse
from pathlib import Path

import comments
import rw_io
import trace

P = rw_io.PATHS


def last_review(ws, before: str) -> str | None:
    dates = [m["date"] for m in trace.load_graph(ws)["meetings"].values()
             if m.get("type") == "advisor-review" and m.get("date", "") < before]
    return max(dates, default=None)


def _fmt(v) -> str:
    return f"{v:.4g}" if isinstance(v, (int, float)) else str(v)


def _cell(v) -> str:
    return str(v if v is not None else "").replace("|", "\\|").replace("\n", " ")


def build_progress(ws, date: str) -> str:
    ws = Path(ws)
    g = trace.load_graph(ws)
    state = g["state"]
    since = last_review(ws, date)
    out = [f"# Progress Review — {date}", "",
           f"งาน: {state.get('title', '-')} · stage: {state.get('stage', '-')} · "
           f"ตั้งแต่ review ครั้งก่อน: {since or '(ครั้งแรก)'}", ""]
    out += ["## 1. สิ่งที่ทำไปแล้ว", ""]
    log = [e for e in rw_io.read_jsonl(ws / P["decision_log"]) if since is None or e["timestamp"][:10] >= since]
    for e in log:
        what = {"advance": f"{e.get('from')} → {e.get('to')}", "approve": f"approve {e.get('gate')}",
                "amend": "protocol amendment"}.get(e["kind"], e["kind"])
        detail = ", ".join(e.get("ids") or [])
        out.append(f"- {e['timestamp'][:10]} {what}" + (f" ({detail})" if detail else "")
                   + (f": {e['reason']}" if e.get("reason") else ""))
    if not log:
        out.append("- (ไม่มีรายการใน decision-log)")
    out += ["", "## 2. ผลการทดลอง", ""]
    if g["results"]:
        out += ["| Result | Experiment | Hypothesis | Metric | Value | CI | Split | Summary |",
                "|---|---|---|---|---|---|---|---|"]
        for rid in sorted(g["results"]):
            r = g["results"][rid]
            hyp = g["experiments"].get(r["experiment_id"], {}).get("hypothesis_id", "-")
            ci = f"[{_fmt(r['ci'][0])}, {_fmt(r['ci'][1])}]" if r.get("ci") else "—"
            out.append("| " + " | ".join(_cell(x) for x in (rid, r["experiment_id"], hyp, r["metric"],
                                                            _fmt(r["value"]), ci, r["split"], r["summary"])) + " |")
    else:
        out.append("_ยังไม่มีผลการทดลอง_")
    out += ["", "## 3. สถานะ comments", "", comments.render_markdown(list(g["comments"].values())).rstrip()]
    out += ["", "## 4. Hypotheses", ""]
    if g["hypotheses"]:
        out += ["| ID | Origin | Status | Based on | Statement |", "|---|---|---|---|---|"]
        for hid, h in sorted(g["hypotheses"].items()):
            out.append("| " + " | ".join(_cell(x) for x in (hid, h.get("origin"), h.get("status"),
                                                            ", ".join(h.get("based_on", [])), h.get("statement"))) + " |")
    else:
        out.append("_ยังไม่มี hypothesis_")
    rep = trace.trace(ws)
    out += ["", "## 5. ประเด็นค้างที่ควรถามอาจารย์", ""]
    pending = [f"- comment {k} ยังเปิดอยู่: {g['comments'][k]['text']}" for k in rep.summary["open_comments"]]
    pending += [f"- {h} อนุมัติแล้วแต่ยังไม่มี experiment" for h in rep.summary["untested_hypotheses"]]
    pending += [f"- trace error: {e}" for e in rep.errors]
    out += pending or ["- (ไม่มีประเด็นค้างจาก artifacts)"]
    out += ["", "<!-- rw-progress: เพิ่มคำถาม/decision ที่ต้องการให้อาจารย์ตัดสินด้านล่าง -->", ""]
    return "\n".join(out)


def write_progress(ws, date: str, force=False) -> Path:
    path = Path(ws) / "progress" / f"{date}-review.md"
    if path.exists() and not force:
        raise FileExistsError(f"{path} already exists (use --force to rebuild it)")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_progress(ws, date), encoding="utf-8")
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build a progress review document for an advisor meeting.")
    ap.add_argument("--workspace")
    ap.add_argument("--date", default=rw_io.today())
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--stdout", action="store_true")
    a = ap.parse_args(argv)
    ws = rw_io.resolve_workspace(a.workspace)
    if a.stdout:
        print(build_progress(ws, a.date))
    else:
        print(f"written: {write_progress(ws, a.date, a.force)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(rw_io.run_cli(main))
