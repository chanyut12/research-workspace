import pytest

import audit
import rw_io
from wsfactory import edit_jsonl, make_good_workspace

P = rw_io.PATHS


@pytest.fixture
def ws(tmp_path):
    return make_good_workspace(tmp_path / "ws")


def codes(a):
    return {i["code"] for i in a["automated_issues"] if i["severity"] == "blocking"}


def test_clean_workspace(ws):
    a = audit.run_automated(ws)
    assert codes(a) == set()
    assert audit.blocking_issues(ws) == []


def test_doi_unverified(ws):
    (ws / P["doi_verification"]).unlink()
    assert "DOI_UNVERIFIED" in codes(audit.run_automated(ws))


def test_doi_not_found(ws):
    rw_io.append_jsonl(ws / P["doi_verification"], {"id": "S-001", "doi": "10.1000/s001", "status": "not-found",
                                                   "detail": "x", "checked_at": "t"})
    assert "DOI_NOT_FOUND" in codes(audit.run_automated(ws))


def test_open_must_comment(ws):
    edit_jsonl(ws / P["comments"], "K-002", severity="must")
    audit.run_automated(ws)
    assert any("K-002" in b for b in audit.blocking_issues(ws))


def test_weaken_verdict_blocks(ws):
    audit.run_automated(ws)
    audit.add_review(ws, "C-001", "WEAKEN", "association, not prediction")
    assert any(b.startswith("C-001: verdict WEAKEN") for b in audit.blocking_issues(ws))


def test_unreviewed_claim_blocks(ws):
    rw_io.append_jsonl(ws / P["claims"], {"id": "C-005", "text": "x", "cites": ["E-001"],
                                          "support_level": "literature", "section": None})
    assert "C-005: no claim review yet" in audit.blocking_issues(ws)


def test_run_preserves_reviews(ws):
    audit.add_review(ws, "C-002", "HUMAN_REVIEW", "check CI")
    a = audit.run_automated(ws)
    assert any(r["claim_id"] == "C-002" and r["verdict"] == "HUMAN_REVIEW" for r in a["claim_reviews"])


def test_missing_audit(ws):
    (ws / P["audit"]).unlink()
    assert audit.blocking_issues(ws) == ["report/audit.json is missing (run audit.py run)"]


def test_review_unknown_claim(ws):
    with pytest.raises(ValueError):
        audit.add_review(ws, "C-099", "PASS")


def test_set_evidence_status(ws):
    audit.set_evidence_status(ws, "E-002", "weaken", "only a discussion remark")
    row = [e for e in rw_io.read_jsonl(ws / P["evidence"]) if e["id"] == "E-002"][0]
    assert row["verification_status"] == "weaken" and row["verification_note"] == "only a discussion remark"
    with pytest.raises(ValueError):
        audit.set_evidence_status(ws, "E-002", "great")
