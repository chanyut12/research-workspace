"""Create a research workspace: folders, state, CLAUDE.md rules, .gitignore and a protocol example."""
from __future__ import annotations

import argparse
from pathlib import Path

import rw_io
import rw_state

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "workspace"
DIRS = ["rw", "protocol/amendments", "literature/raw", "literature/fulltext", "meetings", "synthesis",
        "experiments", "progress", "data", "report"]
MARKER = "research-workbench"


def _render(name: str, title: str) -> str:
    text = (TEMPLATE_DIR / name).read_text(encoding="utf-8")
    return text.replace("{{TITLE}}", title).replace("{{DATE}}", rw_io.today())


def init_workspace(target, title: str) -> Path:
    target = Path(target).resolve()
    if (target / rw_io.PATHS["state"]).exists():
        raise FileExistsError(f"{target} is already a research workspace")
    for d in DIRS:
        (target / d).mkdir(parents=True, exist_ok=True)
    claude = target / "CLAUDE.md"
    if not claude.exists():
        claude.write_text(_render("CLAUDE.md", title), encoding="utf-8")
    elif MARKER not in claude.read_text(encoding="utf-8"):  # keep the user's file, append our rules
        with claude.open("a", encoding="utf-8") as f:
            f.write("\n\n" + _render("CLAUDE.md", title))
    gi = target / ".gitignore"
    have = gi.read_text(encoding="utf-8").splitlines() if gi.exists() else []
    add = [ln for ln in _render("gitignore", title).splitlines() if ln and ln not in have]
    if add:
        prefix = "\n" if have and have[-1].strip() else ""
        with gi.open("a", encoding="utf-8") as f:
            f.write(prefix + "\n".join(add) + "\n")
    example = target / "protocol" / "protocol.example.yaml"
    if not example.exists():
        example.write_text(_render("protocol.example.yaml", title), encoding="utf-8")
    rw_io.write_json(target / rw_io.PATHS["state"], rw_state.new_state(title))
    rw_state.log_decision(target, "init", reason=f"workspace created: {title}")
    return target


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Create a research-workbench workspace.")
    ap.add_argument("directory", nargs="?", default=".")
    ap.add_argument("--title", required=True)
    a = ap.parse_args(argv)
    ws = init_workspace(a.directory, a.title)
    print(f"workspace ready: {ws}")
    return 0


if __name__ == "__main__":
    raise SystemExit(rw_io.run_cli(main))
