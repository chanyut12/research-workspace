import pytest

import init_workspace
import rw_io
import trace
import validate


def test_init_creates_valid_workspace(tmp_path):
    ws = init_workspace.init_workspace(tmp_path / "stroke study", "Stroke outcome")
    for d in ("rw", "protocol/amendments", "literature/raw", "literature/fulltext", "meetings",
              "synthesis", "experiments", "progress", "data", "report"):
        assert (ws / d).is_dir(), d
    state = rw_io.read_json(ws / "rw" / "state.json")
    assert state["stage"] == "INIT" and state["title"] == "Stroke outcome"
    assert validate.validate_workspace(ws) == []
    assert trace.trace(ws).ok
    assert "Stroke outcome" in (ws / "CLAUDE.md").read_text(encoding="utf-8")
    assert "data/" in (ws / ".gitignore").read_text(encoding="utf-8")
    assert (ws / "protocol" / "protocol.example.yaml").exists()
    assert rw_io.read_jsonl(ws / "rw" / "decision-log.jsonl")[0]["kind"] == "init"


def test_init_twice_refused(tmp_path):
    init_workspace.init_workspace(tmp_path, "A")
    with pytest.raises(FileExistsError):
        init_workspace.init_workspace(tmp_path, "A")


def test_existing_project_files_are_appended_not_overwritten(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# My stroke project\nkeep me\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("*.ipynb_checkpoints\ndata/\n", encoding="utf-8")
    init_workspace.init_workspace(tmp_path, "A")
    claude = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert claude.startswith("# My stroke project\nkeep me\n") and "research-workbench" in claude
    gi = (tmp_path / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert gi.count("data/") == 1 and "*.ipynb_checkpoints" in gi and "literature/fulltext/" in gi
