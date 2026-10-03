import pytest

import meeting
import rw_io
import trace
import validate
from wsfactory import make_good_workspace

P = rw_io.PATHS


@pytest.fixture
def ws(tmp_path):
    return make_good_workspace(tmp_path / "my ws")


def test_new_meeting(ws):
    d = meeting.new_meeting(ws, "expert-consult", "2026-10-20", ["clinician", "PhD student"], ["label definition"])
    assert d.name == "M-003-2026-10-20-expert-consult"
    assert validate.validate_file(d / "meeting.yaml", ws) == []
    assert (d / "notes.md").exists()


def test_new_meeting_validation(ws):
    with pytest.raises(ValueError, match="type"):
        meeting.new_meeting(ws, "chat", "2026-10-20", ["x"])
    with pytest.raises(ValueError, match="date"):
        meeting.new_meeting(ws, "self-note", "20/10/2026", ["x"])
    with pytest.raises(ValueError, match="role"):
        meeting.new_meeting(ws, "self-note", "2026-10-20", [])


def test_add_observation_paraphrase(ws):
    o = meeting.add_observation(ws, "M-001", "clinician", "Night onset delays arrival", "paraphrase",
                                "clinical-experience", "notes.md:3")
    assert o["id"] == "O-003" and o["confirmed_by_user"] is True
    assert validate.validate_file(ws / P["observations"], ws) == []
    assert trace.trace(ws).ok


def test_verbatim_must_be_in_notes(ws):
    with pytest.raises(ValueError, match="verbatim"):
        meeting.add_observation(ws, "M-001", "clinician", "something never said", "verbatim",
                                "anecdote", "notes.md:9")
    o = meeting.add_observation(ws, "M-001", "clinician", "glucose   แรกรับอาจสัมพันธ์กับ  outcome",
                                "verbatim", "clinical-experience", "notes.md:4")
    assert o["form"] == "verbatim"


def test_verbatim_from_transcript(ws, tmp_path):
    t = tmp_path / "zoom.txt"
    t.write_text("00:12:30 Advisor: try calibration plots as well\n", encoding="utf-8")
    meeting.attach_transcript(ws, "M-002", t)
    assert (ws / "meetings" / "M-002-2026-10-10-advisor-review" / "transcript.txt").exists()
    o = meeting.add_observation(ws, "M-002", "advisor", "try calibration plots as well", "verbatim",
                                "domain-rule", "transcript 00:12:30")
    assert o["meeting_id"] == "M-002"


def test_speaker_must_be_participant(ws):
    with pytest.raises(ValueError, match="participant"):
        meeting.add_observation(ws, "M-001", "advisor", "x", "paraphrase", "anecdote", "notes.md:1")


def test_unknown_meeting(ws):
    with pytest.raises(ValueError, match="unknown meeting"):
        meeting.add_comment(ws, "M-404", "general", "x", "must", "n")


def test_add_comment(ws):
    with pytest.raises(ValueError, match="target"):
        meeting.add_comment(ws, "M-002", "X-404", "x", "must", "notes.md:2")
    k = meeting.add_comment(ws, "M-002", "H-002", "ต้องนิยาม night onset ให้ชัด", "should", "notes.md:3")
    assert k["id"] == "K-003" and k["status"] == "open"
    assert validate.validate_file(ws / P["comments"], ws) == []


def test_prep_and_logged(ws):
    meeting.set_prep_questions(ws, "M-002", ["Is AUROC enough?"])
    meeting.mark_logged(ws, "M-002")
    m = rw_io.read_yaml(ws / "meetings" / "M-002-2026-10-10-advisor-review" / "meeting.yaml")
    assert m["prep_questions"] == ["Is AUROC enough?"] and m["logged"] is True
