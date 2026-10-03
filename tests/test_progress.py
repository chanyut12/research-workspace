import pytest

import progress
import rw_io
from wsfactory import make_good_workspace


@pytest.fixture
def ws(tmp_path):
    return make_good_workspace(tmp_path / "ws")


def test_build_progress(ws):
    md = progress.build_progress(ws, "2026-10-20")
    assert "ตั้งแต่ review ครั้งก่อน: 2026-10-10" in md
    assert "approve G3" in md and "approve G1" not in md   # only entries since the last review
    assert "| R-001 | X-001 | H-001 | auroc | 0.81 | [0.78, 0.84]" in md
    assert "K-001" in md and "K-002" in md
    assert "| H-002 | expert | approved |" in md
    section5 = md.split("## 5.")[1]
    assert "K-002" in section5 and "H-002" in section5


def test_first_review(tmp_path):
    rw_io.write_json(tmp_path / "rw" / "state.json", {"title": "T", "stage": "INIT", "gates": {}})
    md = progress.build_progress(tmp_path, "2026-10-20")
    assert "(ครั้งแรก)" in md and "_ไม่มี comments_" in md


def test_write_progress_no_overwrite(ws):
    p = progress.write_progress(ws, "2026-10-20")
    assert p.name == "2026-10-20-review.md"
    with pytest.raises(FileExistsError):
        progress.write_progress(ws, "2026-10-20")
    assert progress.write_progress(ws, "2026-10-20", force=True) == p
