import pytest

import net
import rw_io
import verify_doi
from wsfactory import make_good_workspace

REC = {"id": "S-001", "title": "Admission NIHSS predicts functional outcome after ischemic stroke",
       "year": 2019, "doi": "10.1000/s001"}


def msg(title=REC["title"], year=2019, **extra):
    return {"title": [title], "issued": {"date-parts": [[year, 5]]}, **extra}


def test_compare_verified_and_year_tolerance():
    assert verify_doi.compare(REC, msg())[0] == "verified"
    assert verify_doi.compare(REC, msg(year=2020))[0] == "verified"


def test_compare_mismatch():
    status, detail = verify_doi.compare(REC, msg(title="Something else entirely", year=2012))
    assert status == "metadata-mismatch" and "title" in detail and "year" in detail


def test_compare_retraction():
    status, _ = verify_doi.compare(REC, msg(**{"updated-by": [{"type": "retraction"}]}))
    assert status == "retracted-check-needed"


def test_verify_record_paths():
    def nf(url, params=None, headers=None):
        raise net.NotFound("404")

    def down(url, params=None, headers=None):
        raise net.RetrievalError("down")
    assert verify_doi.verify_record(REC, fetch=nf)["status"] == "not-found"
    assert verify_doi.verify_record(REC, fetch=down)["status"] == "error"
    assert verify_doi.verify_record({**REC, "doi": None})["status"] == "no-doi"


def test_verify_workspace(tmp_path):
    ws = make_good_workspace(tmp_path / "ws")
    (ws / rw_io.PATHS["doi_verification"]).unlink()
    titles = {r["doi"]: r for r in rw_io.read_jsonl(ws / rw_io.PATHS["records"])}
    calls = []

    def fetch(url, params=None, headers=None):
        doi = url.rsplit("works/", 1)[1]
        calls.append(doi)
        r = titles[doi]
        return {"message": msg(title=r["title"], year=r["year"])}
    results = verify_doi.verify_workspace(ws, scope="evidence", fetch=fetch)
    assert [r["status"] for r in results] == ["verified", "verified"]
    assert sorted(calls) == ["10.1000/s001", "10.1000/s002"]
    assert len(rw_io.read_jsonl(ws / rw_io.PATHS["doi_verification"])) == 2


def test_datacite_doi_verified():
    from test_import_papers import datacite_only
    rec = {"id": "S-009", "title": "Attention Is All You Need", "year": 2017, "doi": "10.48550/arxiv.1706.03762"}
    r = verify_doi.verify_record(rec, fetch=datacite_only)
    assert r["status"] == "verified" and "DataCite" in r["detail"]
