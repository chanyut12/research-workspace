import pytest

import dedupe
import rw_io
import validate

P = rw_io.PATHS


def cand(title, year=2020, doi=None, qid="Q-001", source="openalex", **ids):
    return {"title": title, "year": year, "doi": doi, "identifiers": ids, "abstract": None, "authors": [],
            "venue": None, "url": None, "source": source, "query_id": qid, "retrieved_at": "t"}


@pytest.fixture
def ws(tmp_path):
    rw_io.write_json(tmp_path / P["state"], {})
    return tmp_path


def test_normalize_doi():
    assert dedupe.normalize_doi("https://doi.org/10.1000/ABC") == "10.1000/abc"
    assert dedupe.normalize_doi("doi:10.1/x ") == "10.1/x"
    assert dedupe.normalize_doi("not a doi") is None
    assert dedupe.normalize_doi(None) is None


def test_normalize_title():
    assert dedupe.normalize_title("Stroke: Outcome—Prediction!") == "stroke outcome prediction"


def test_merge_same_doi_different_case(ws):
    rw_io.write_jsonl(ws / P["candidates"], [cand("A study", doi="10.1/AB"),
                                            cand("A study.", doi="https://doi.org/10.1/ab", qid="Q-002",
                                                 source="crossref")])
    assert dedupe.merge_candidates(ws) == {"new": 1, "merged": 1, "skipped": 0}
    recs = rw_io.read_jsonl(ws / P["records"])
    assert len(recs) == 1 and recs[0]["sources"] == ["openalex", "crossref"]
    assert recs[0]["query_ids"] == ["Q-001", "Q-002"]
    assert validate.validate_file(ws / P["records"], ws) == []


def test_merge_by_title_year_when_no_doi(ws):
    rw_io.write_jsonl(ws / P["candidates"], [cand("Glucose and Stroke", doi=None),
                                            cand("glucose and stroke", doi="10.1/g", qid="Q-002")])
    dedupe.merge_candidates(ws)
    recs = rw_io.read_jsonl(ws / P["records"])
    assert len(recs) == 1 and recs[0]["doi"] == "10.1/g"


def test_different_dois_not_merged(ws):
    rw_io.write_jsonl(ws / P["candidates"], [cand("Same title", doi="10.1/a"), cand("Same title", doi="10.1/b")])
    dedupe.merge_candidates(ws)
    assert [r["id"] for r in rw_io.read_jsonl(ws / P["records"])] == ["S-001", "S-002"]


def test_ids_continue_and_candidates_cleared(ws):
    rw_io.write_jsonl(ws / P["records"], [{"id": "S-007", "title": "Old", "year": 2001, "doi": None,
                                           "identifiers": {}, "sources": ["openalex"], "query_ids": ["Q-001"]}])
    rw_io.write_jsonl(ws / P["candidates"], [cand("New one"), cand("   ")])
    assert dedupe.merge_candidates(ws) == {"new": 1, "merged": 0, "skipped": 1}
    assert rw_io.read_jsonl(ws / P["records"])[-1]["id"] == "S-008"
    assert rw_io.read_jsonl(ws / P["candidates"]) == []
    assert len(rw_io.read_csv(ws / P["dedupe_log"])) == 1
    assert dedupe.merge_candidates(ws) == {"new": 0, "merged": 0, "skipped": 0}


def test_arxiv_match(ws):
    rw_io.write_jsonl(ws / P["candidates"], [cand("Preprint", year=2023, arxiv="2301.1"),
                                            cand("Published version", year=2024, arxiv="2301.1")])
    dedupe.merge_candidates(ws)
    assert len(rw_io.read_jsonl(ws / P["records"])) == 1
