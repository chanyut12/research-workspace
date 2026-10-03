"""Meetings (M-xxx) with clinicians and advisors: create, prep questions, and record
user-confirmed observations (O-xxx) and comments (K-xxx)."""
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

import ids
import rw_io

P = rw_io.PATHS
MEETING_TYPES = ("expert-consult", "advisor-review", "self-note")
FORMS = ("verbatim", "paraphrase")
BASES = ("clinical-experience", "domain-rule", "anecdote", "data-impression")
SEVERITIES = ("must", "should", "consider")


def new_meeting(ws, mtype, date, roles, agenda=None) -> Path:
    with rw_io.workspace_lock(ws):
        return _new_meeting(ws, mtype, date, roles, agenda)


def _new_meeting(ws, mtype, date, roles, agenda=None) -> Path:
    ws = Path(ws)
    if mtype not in MEETING_TYPES:
        raise ValueError(f"meeting type must be one of {', '.join(MEETING_TYPES)}")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date or ""):
        raise ValueError("date must be YYYY-MM-DD")
    roles = [r.strip() for r in roles or [] if r.strip()]
    if not roles:
        raise ValueError("at least one participant role is required (e.g. --role clinician)")
    mid = ids.next_id(ws, "M")
    d = ws / "meetings" / f"{mid}-{date}-{mtype}"
    rw_io.write_yaml(d / "meeting.yaml", {
        "id": mid, "type": mtype, "date": date, "participants": [{"role": r, "name": None} for r in roles],
        "agenda": list(agenda or []), "prep_questions": [], "notes_file": "notes.md", "transcript_file": None,
        "logged": False})
    (d / "notes.md").write_text(f"# {mid} — {mtype} — {date}\n\n<!-- จด notes ที่นี่: bullet สั้น ๆ ไทย/อังกฤษได้ -->\n",
                                encoding="utf-8")
    return d


def meeting_dir(ws, mid) -> Path:
    matches = sorted((Path(ws) / "meetings").glob(f"{mid}-*/meeting.yaml"))
    if not matches:
        raise ValueError(f"unknown meeting {mid}")
    return matches[0].parent


def _load(ws, mid) -> tuple[Path, dict]:
    d = meeting_dir(ws, mid)
    return d, rw_io.read_yaml(d / "meeting.yaml")


def _norm(s) -> str:
    return " ".join(str(s).split()).lower()


def _source_text(d, m) -> str:
    parts = []
    for key in ("notes_file", "transcript_file"):
        if m.get(key) and (d / m[key]).exists():
            parts.append((d / m[key]).read_text(encoding="utf-8"))
    return "\n".join(parts)


def set_prep_questions(ws, mid, questions) -> dict:
    d, m = _load(ws, mid)
    m["prep_questions"] = [q for q in questions if q.strip()]
    rw_io.write_yaml(d / "meeting.yaml", m)
    return m


def attach_transcript(ws, mid, file) -> Path:
    d, m = _load(ws, mid)
    src = Path(file)
    if not src.is_file():
        raise ValueError(f"transcript file not found: {src}")
    dest = d / f"transcript{src.suffix or '.txt'}"
    shutil.copyfile(src, dest)
    m["transcript_file"] = dest.name
    rw_io.write_yaml(d / "meeting.yaml", m)
    return dest


def add_observation(ws, meeting_id, speaker_role, statement, form, basis, source_ref) -> dict:
    with rw_io.workspace_lock(ws):
        return _add_observation(ws, meeting_id, speaker_role, statement, form, basis, source_ref)


def _add_observation(ws, meeting_id, speaker_role, statement, form, basis, source_ref) -> dict:
    """Call only after the user confirmed this observation."""
    ws = Path(ws)
    d, m = _load(ws, meeting_id)
    if form not in FORMS:
        raise ValueError(f"form must be one of {', '.join(FORMS)}")
    if basis not in BASES:
        raise ValueError(f"basis must be one of {', '.join(BASES)}")
    roles = [p["role"] for p in m.get("participants", [])]
    if speaker_role not in roles:
        raise ValueError(f"speaker role {speaker_role!r} is not a participant of {meeting_id} ({', '.join(roles)})")
    if not (statement or "").strip():
        raise ValueError("statement is empty")
    if form == "verbatim" and _norm(statement) not in _norm(_source_text(d, m)):
        raise ValueError("form=verbatim requires the statement to appear in notes.md or the transcript; "
                         "use paraphrase otherwise")
    obs = {"id": ids.next_id(ws, "O"), "meeting_id": meeting_id, "speaker_role": speaker_role,
           "statement": statement.strip(), "form": form, "basis": basis, "source_ref": source_ref,
           "confirmed_by_user": True, "recorded_at": rw_io.now_iso()}
    rw_io.append_jsonl(ws / P["observations"], obs)
    return obs


def add_comment(ws, meeting_id, target, text, severity, source_ref) -> dict:
    with rw_io.workspace_lock(ws):
        return _add_comment(ws, meeting_id, target, text, severity, source_ref)


def _add_comment(ws, meeting_id, target, text, severity, source_ref) -> dict:
    """Call only after the user confirmed this comment."""
    ws = Path(ws)
    meeting_dir(ws, meeting_id)
    if severity not in SEVERITIES:
        raise ValueError(f"severity must be one of {', '.join(SEVERITIES)}")
    prefix = target.split("-")[0]
    if target != "general" and (prefix not in ("H", "X", "R", "C") or target not in ids.existing_ids(ws, prefix)):
        raise ValueError(f"target {target!r} must be 'general' or an existing H/X/R/C ID")
    if not (text or "").strip():
        raise ValueError("comment text is empty")
    k = {"id": ids.next_id(ws, "K"), "meeting_id": meeting_id, "target": target, "text": text.strip(),
         "severity": severity, "status": "open", "resolution": None, "changed_ids": [], "deferred_until": None,
         "source_ref": source_ref, "confirmed_by_user": True, "updated_at": rw_io.now_iso()}
    rw_io.append_jsonl(ws / P["comments"], k)
    return k


def mark_logged(ws, mid) -> dict:
    d, m = _load(ws, mid)
    m["logged"] = True
    rw_io.write_yaml(d / "meeting.yaml", m)
    return m


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Record meetings, observations (O) and comments (K).")
    ap.add_argument("--workspace")
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new", parents=[rw_io.ws_parent()])
    n.add_argument("--type", required=True, choices=MEETING_TYPES)
    n.add_argument("--date", default=rw_io.today())
    n.add_argument("--role", action="append", default=[], help="participant role (repeat)")
    n.add_argument("--agenda", action="append", default=[])
    pq = sub.add_parser("prep", parents=[rw_io.ws_parent()])
    pq.add_argument("meeting_id")
    pq.add_argument("--question", action="append", default=[])
    ao = sub.add_parser("add-observation", parents=[rw_io.ws_parent()])
    ao.add_argument("meeting_id")
    ao.add_argument("--role", required=True)
    ao.add_argument("--statement", required=True)
    ao.add_argument("--form", required=True, choices=FORMS)
    ao.add_argument("--basis", required=True, choices=BASES)
    ao.add_argument("--ref", required=True, help="where in notes/transcript, e.g. notes.md:5")
    ac = sub.add_parser("add-comment", parents=[rw_io.ws_parent()])
    ac.add_argument("meeting_id")
    ac.add_argument("--target", required=True)
    ac.add_argument("--text", required=True)
    ac.add_argument("--severity", required=True, choices=SEVERITIES)
    ac.add_argument("--ref", required=True)
    at = sub.add_parser("attach-transcript", parents=[rw_io.ws_parent()])
    at.add_argument("meeting_id")
    at.add_argument("file")
    lg = sub.add_parser("logged", parents=[rw_io.ws_parent()])
    lg.add_argument("meeting_id")
    a = ap.parse_args(argv)
    ws = rw_io.resolve_workspace(a.workspace)
    if a.cmd == "new":
        d = new_meeting(ws, a.type, a.date, a.role, a.agenda)
        print(f"{d.name}: write notes in {d / 'notes.md'}")
    elif a.cmd == "prep":
        print(f"{len(set_prep_questions(ws, a.meeting_id, a.question)['prep_questions'])} prep question(s) saved")
    elif a.cmd == "add-observation":
        print(add_observation(ws, a.meeting_id, a.role, a.statement, a.form, a.basis, a.ref)["id"])
    elif a.cmd == "add-comment":
        print(add_comment(ws, a.meeting_id, a.target, a.text, a.severity, a.ref)["id"])
    elif a.cmd == "attach-transcript":
        print(f"transcript saved: {attach_transcript(ws, a.meeting_id, a.file)}")
    else:
        mark_logged(ws, a.meeting_id)
        print(f"{a.meeting_id} logged")
    return 0


if __name__ == "__main__":
    raise SystemExit(rw_io.run_cli(main))
