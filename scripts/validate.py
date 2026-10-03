"""Validate research workspace artifacts against schemas/ (one schema per artifact type)."""
from __future__ import annotations

import argparse
import json
import os
from fnmatch import fnmatch
from functools import lru_cache
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

import rw_io

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"
RULES = [  # (path pattern relative to workspace, schema name, file kind)
    ("rw/state.json", "state", "json"),
    ("rw/decision-log.jsonl", "decision", "jsonl"),
    ("protocol/protocol.yaml", "protocol", "yaml"),
    ("literature/search-log.csv", "search_log_row", "csv"),
    ("literature/records.jsonl", "record", "jsonl"),
    ("literature/screening.csv", "screening_row", "csv"),
    ("literature/evidence.jsonl", "evidence", "jsonl"),
    ("meetings/*/meeting.yaml", "meeting", "yaml"),
    ("meetings/observations.jsonl", "observation", "jsonl"),
    ("meetings/comments.jsonl", "comment", "jsonl"),
    ("synthesis/hypotheses.yaml", "hypotheses", "yaml"),
    ("experiments/*/spec.yaml", "experiment", "yaml"),
    ("experiments/*/runs.jsonl", "run", "jsonl"),
    ("experiments/*/results.jsonl", "result", "jsonl"),
    ("report/claims.jsonl", "claim", "jsonl"),
    ("report/audit.json", "audit", "json"),
]
ID_FIELD = {"record": "id", "evidence": "id", "observation": "id", "comment": "id",
            "result": "id", "claim": "id", "run": "run_id"}
SKIP_DIRS = {"data", ".git", ".venv"}


@lru_cache(maxsize=None)
def _validator(name: str) -> Draft202012Validator:
    schema = json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def rule_for(rel: str) -> tuple[str, str] | None:
    rel = rel.replace("\\", "/")
    for pattern, name, kind in RULES:
        if fnmatch(rel, pattern):
            return name, kind
    return None


def validate_object(name: str, obj, rel: str = "-", loc="-") -> list[str]:
    out = []
    for err in sorted(_validator(name).iter_errors(obj), key=lambda e: str(list(e.absolute_path))):
        field = "/".join(str(p) for p in err.absolute_path) or "(root)"
        out.append(f"{rel}:{loc}: {field}: {err.message}")
    return out


def _load_items(path: Path, kind: str) -> list[tuple]:
    if kind == "json":
        return [("-", rw_io.read_json(path))]
    if kind == "yaml":
        return [("-", rw_io.read_yaml(path))]
    if kind == "jsonl":
        return rw_io.read_jsonl_numbered(path)
    return list(enumerate(rw_io.read_csv(path), 2))  # row 1 is the header


def validate_file(path, ws) -> list[str]:
    path, ws = Path(path).resolve(), Path(ws).resolve()
    try:
        rel = path.relative_to(ws).as_posix()
    except ValueError:
        return [f"{path}: not inside workspace {ws}"]
    rule = rule_for(rel)
    if rule is None or not path.exists():
        return []
    name, kind = rule
    try:
        items = _load_items(path, kind)
    except (ValueError, yaml.YAMLError) as e:
        return [f"{rel}: cannot parse: {e}"]
    errors = []
    for loc, obj in items:
        errors += validate_object(name, obj, rel, loc)
    key = ID_FIELD.get(name)
    if key:
        seen = {}
        for loc, obj in items:
            v = obj.get(key) if isinstance(obj, dict) else None
            if v and v in seen:
                errors.append(f"{rel}:{loc}: {key}: duplicate id {v} (first at line {seen[v]})")
            elif v:
                seen[v] = loc
    if name == "hypotheses" and items and isinstance(items[0][1], dict):
        ids = [h.get("id") for h in items[0][1].get("hypotheses") or [] if isinstance(h, dict)]
        errors += [f"{rel}:-: hypotheses: duplicate id {d}" for d in sorted({i for i in ids if i and ids.count(i) > 1})]
    return errors


def validate_workspace(ws) -> list[str]:
    ws = Path(ws).resolve()
    errors = []
    for dirpath, dirnames, filenames in os.walk(ws):
        if Path(dirpath) == ws:
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        dirnames.sort()
        for fn in sorted(filenames):
            path = Path(dirpath) / fn
            if rule_for(path.relative_to(ws).as_posix()):
                errors += validate_file(path, ws)
    return errors


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Validate research workspace artifacts against schemas/.")
    ap.add_argument("files", nargs="*", help="artifact files to check (default: whole workspace)")
    ap.add_argument("--workspace")
    a = ap.parse_args(argv)
    ws = rw_io.resolve_workspace(a.workspace or (a.files[0] if a.files else None))
    errors = []
    if a.files:
        for f in a.files:
            errors += validate_file(Path(f), ws)
    else:
        errors = validate_workspace(ws)
    for e in errors:
        print(e)
    if not errors:
        print("OK: all artifacts valid")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(rw_io.run_cli(main))
