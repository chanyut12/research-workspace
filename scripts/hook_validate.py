"""PostToolUse hook: after Write/Edit of a workspace artifact, validate it; exit 2 sends errors to Claude."""
import json
import sys
from pathlib import Path


def main(stdin=None) -> int:
    try:
        import rw_io
        import validate
    except ImportError:  # deps missing on this Python: never block the user's work
        print("research-workbench: pyyaml/jsonschema not installed; artifact validation skipped", file=sys.stderr)
        return 0
    data = json.load(stdin or sys.stdin)
    fp = (data.get("tool_input") or {}).get("file_path")
    if not fp:
        return 0
    path = Path(fp)
    if not path.is_absolute():
        path = Path(data.get("cwd") or ".") / path
    ws = rw_io.find_workspace(path)
    if ws is None:
        return 0
    try:
        rel = path.resolve().relative_to(ws).as_posix()
    except ValueError:
        return 0
    if validate.rule_for(rel) is None:
        return 0
    errors = validate.validate_file(path, ws)
    if errors:
        print("\n".join(errors) + f"\nFix {rel} so it matches schemas/ (research-workbench).", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
