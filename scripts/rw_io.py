"""Shared file I/O and workspace helpers for research-workbench scripts."""
from __future__ import annotations

import argparse
import contextlib
import csv
import datetime as _dt
import fcntl
import json
import sys
from pathlib import Path
from typing import Any, Callable

PATHS = {
    "state": "rw/state.json",
    "decision_log": "rw/decision-log.jsonl",
    "protocol": "protocol/protocol.yaml",
    "search_log": "literature/search-log.csv",
    "candidates": "literature/candidates.jsonl",
    "dedupe_log": "literature/dedupe-log.csv",
    "records": "literature/records.jsonl",
    "screening": "literature/screening.csv",
    "evidence": "literature/evidence.jsonl",
    "retrieval_errors": "literature/retrieval-errors.jsonl",
    "doi_verification": "literature/doi-verification.jsonl",
    "observations": "meetings/observations.jsonl",
    "comments": "meetings/comments.jsonl",
    "hypotheses": "synthesis/hypotheses.yaml",
    "claims": "report/claims.jsonl",
    "report": "report/report.md",
    "audit": "report/audit.json",
}
SEARCH_LOG_FIELDS = ["query_id", "purpose", "for_id", "source", "query", "filters",
                     "timestamp", "count", "raw_file", "status"]
SCREENING_FIELDS = ["id", "stage", "decision", "reason_code", "confidence", "reviewer",
                    "timestamp", "protocol_version"]
DEDUPE_LOG_FIELDS = ["timestamp", "query_id", "title", "action", "record_id", "key"]


class NotInWorkspace(Exception):
    pass


def find_workspace(start: Path) -> Path | None:
    """Return the nearest directory (start or a parent) that contains rw/state.json."""
    p = Path(start).resolve()
    if not p.is_dir():
        p = p.parent
    for d in (p, *p.parents):
        if (d / PATHS["state"]).is_file():
            return d
    return None


def resolve_workspace(arg: str | None = None) -> Path:
    ws = find_workspace(Path(arg) if arg else Path.cwd())
    if ws is None:
        raise NotInWorkspace("not inside a research workspace (no rw/state.json found); "
                             "run /rw-init first or pass --workspace")
    return ws


def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def today() -> str:
    return _dt.date.today().isoformat()


@contextlib.contextmanager
def workspace_lock(ws):
    """Exclusive lock for "allocate ID + append" sequences, so parallel agents never collide.
    Not re-entrant: never call a locked function while holding the lock."""
    p = Path(ws) / "rw" / ".lock"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def ws_parent() -> argparse.ArgumentParser:
    """Parent parser so --workspace also works after a subcommand."""
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--workspace", default=argparse.SUPPRESS, help="workspace directory (default: from cwd)")
    return p


def _ensure_trailing_newline(path: Path, newline: str) -> None:
    if path.exists() and path.stat().st_size > 0:
        with path.open("rb") as f:
            f.seek(-1, 2)
            last = f.read(1)
        if last not in (b"\n", b"\r"):
            with path.open("a", encoding="utf-8", newline="") as f:
                f.write(newline)


def read_json(path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, obj) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_jsonl_numbered(path) -> list[tuple[int, Any]]:
    path = Path(path)
    if not path.exists():
        return []
    rows = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append((n, json.loads(line)))
        except json.JSONDecodeError as e:
            raise ValueError(f"{path}:{n}: invalid JSON: {e.msg}") from None
    return rows


def read_jsonl(path) -> list[Any]:
    return [row for _, row in read_jsonl_numbered(path)]


def write_jsonl(path, rows) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def append_jsonl(path, obj) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _ensure_trailing_newline(path, "\n")
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def read_yaml(path) -> Any:
    path = Path(path)
    if not path.exists():
        return None
    import yaml  # imported lazily so stdlib-only callers (hooks) work without pyyaml
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def write_yaml(path, obj) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    import yaml
    path.write_text(yaml.safe_dump(obj, allow_unicode=True, sort_keys=False), encoding="utf-8")


def read_csv(path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def append_csv(path, row: dict, fieldnames: list[str]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists() or path.stat().st_size == 0
    _ensure_trailing_newline(path, "\r\n")
    with path.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if new:
            w.writeheader()
        w.writerow({k: "" if row.get(k) is None else str(row[k]) for k in fieldnames})


def run_cli(main_fn: Callable, argv=None) -> int:
    """Run a script's main() and turn expected errors into a one-line message + exit 1."""
    try:
        return main_fn(argv) or 0
    except (NotInWorkspace, ValueError, FileExistsError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
