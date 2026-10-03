import json
from pathlib import Path

import pytest

import net
import rw_io
import search
import validate

P = rw_io.PATHS
FIX = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


@pytest.fixture
def ws(tmp_path):
    rw_io.write_json(tmp_path / P["state"], {})
    rw_io.write_yaml(tmp_path / P["protocol"], {"date_range": {"from_year": 2015, "to_year": 2026}})
    return tmp_path


def test_parse_openalex():
    a, b = search.parse("openalex", load("openalex_works.json"))
    assert a["doi"] == "10.1000/s001" and a["identifiers"]["pmid"] == "31234567"
    assert a["abstract"] == "NIHSS predicts outcome" and a["venue"] == "Stroke" and a["authors"] == ["Ann Author"]
    assert b["title"] == "Glucose and stroke" and b["doi"] is None and b["venue"] is None


def test_parse_crossref():
    (a,) = search.parse("crossref", load("crossref_works.json"))
    assert (a["doi"], a["year"], a["authors"], a["abstract"], a["venue"]) == \
        ("10.1000/s002", 2022, ["Bo Lee"], "We trained models.", "J Stroke")


def test_parse_s2():
    (a,) = search.parse("semantic_scholar", load("s2_search.json"))
    assert a["identifiers"] == {"s2": "abc123", "arxiv": "2301.00001", "pmid": "37000000"}
    assert a["doi"] == "10.1000/s003"


def test_build_request_filters(monkeypatch):
    url, params, headers = search.build_request("openalex", "stroke", 2015, 2026, 50)
    assert params["filter"] == "publication_year:2015-2026"
    _, params, _ = search.build_request("crossref", "stroke", 2015, None, 500)
    assert params["filter"] == "from-pub-date:2015" and params["rows"] == 100
    monkeypatch.setenv("S2_API_KEY", "k")
    _, params, headers = search.build_request("semantic_scholar", "stroke", None, 2020, 10)
    assert params["year"] == "-2020" and headers == {"x-api-key": "k"}


def test_run_search_logs_everything(ws):
    seen = {}

    def fetch(url, params=None, headers=None):
        seen["params"] = params
        return load("openalex_works.json")
    row = search.run_search(ws, "openalex", "stroke outcome", "scoping", "", fetch=fetch)
    assert row["query_id"] == "Q-001" and row["count"] == 2 and row["status"] == "ok"
    assert seen["params"]["filter"] == "publication_year:2015-2026"  # protocol date range by default
    assert (ws / "literature" / "raw" / "Q-001-openalex.json").exists()
    cands = rw_io.read_jsonl(ws / P["candidates"])
    assert [c["query_id"] for c in cands] == ["Q-001", "Q-001"] and cands[0]["source"] == "openalex"
    assert validate.validate_file(ws / P["search_log"], ws) == []


def test_run_search_failure_is_logged_not_faked(ws):
    def fetch(url, params=None, headers=None):
        raise net.RetrievalError("failed after 3 attempts")
    with pytest.raises(net.RetrievalError):
        search.run_search(ws, "crossref", "stroke", "supporting", "", fetch=fetch)
    assert rw_io.read_csv(ws / P["search_log"])[0]["status"] == "error"
    assert rw_io.read_jsonl(ws / P["retrieval_errors"])[0]["query_id"] == "Q-001"
    assert rw_io.read_jsonl(ws / P["candidates"]) == []


def test_invalid_for_id(ws):
    with pytest.raises(ValueError, match="for_id"):
        search.run_search(ws, "openalex", "x", "supporting", "Hyp-1", fetch=lambda *a, **k: {})
    with pytest.raises(ValueError, match="does not exist"):
        search.run_search(ws, "openalex", "x", "supporting", "H-001", fetch=lambda *a, **k: {})


def test_cli_exit_2_on_failure(ws, monkeypatch, capsys):
    def boom(*a, **k):
        raise net.RetrievalError("down")
    monkeypatch.setattr(net, "get_json", boom)
    code = search.main(["--workspace", str(ws), "--source", "openalex", "--query", "x", "--purpose", "scoping"])
    assert code == 2 and "do not substitute" in capsys.readouterr().err
