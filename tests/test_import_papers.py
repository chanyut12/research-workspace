"""Import papers the user downloaded (e.g. from Google Scholar) as PDFs, optionally with their own .md."""
import pytest

import import_papers
import net
import rw_io
import trace
import validate
from pdfgen import make_pdf
from wsfactory import make_good_workspace

P = rw_io.PATHS
NEW_TITLE = "Thrombolysis timing and functional outcome after ischemic stroke"
PAGES = {
    "thrombo.pdf": [f"{NEW_TITLE}\nJ Stroke Res 2021 doi:10.1000/S009.", "Results\nOR 1.32 for late treatment"],
    "notitle.pdf": ["Admission glucose and early neurological deterioration in stroke", "Methods text"],
    "ambiguous.pdf": ["Stroke outcome prediction with machine learning models", "x"],
    "old.pdf": ["Some header\nhttps://doi.org/10.1000/s001", "Results"],
    "scan.pdf": ["", ""],
    "mine.pdf": ["Atrial fibrillation and onset to door time in acute stroke", "body"],
}


def fake_converter(path):
    return PAGES[path.name]


def fake_fetch(url, params=None, headers=None):
    if url.endswith("/works/10.1000/s009"):
        return {"message": {"DOI": "10.1000/S009", "title": [NEW_TITLE], "issued": {"date-parts": [[2021]]},
                            "author": [{"given": "Kim", "family": "Lee"}], "container-title": ["J Stroke Res"]}}
    if url.endswith("/works/10.1000/s001"):
        return {"message": {"DOI": "10.1000/s001",
                            "title": ["Admission NIHSS predicts functional outcome after ischemic stroke"],
                            "issued": {"date-parts": [[2019]]}}}
    if url == "https://api.openalex.org/works":
        q = params["search"]
        if q.startswith("Admission glucose"):
            return {"results": [{"id": "https://openalex.org/W5", "title": q, "publication_year": 2020,
                                 "doi": "https://doi.org/10.1000/g5"}]}
        if q.startswith("Atrial fibrillation"):
            return {"results": [{"id": "https://openalex.org/W6", "title": q, "publication_year": 2018, "doi": None}]}
        if q.startswith("Stroke outcome prediction"):
            return {"results": [{"id": "W7", "title": q, "publication_year": 2020, "doi": "https://doi.org/10.1/a"},
                                {"id": "W8", "title": q + ".", "publication_year": 2022, "doi": "https://doi.org/10.1/b"}]}
        return {"results": []}
    raise net.NotFound(url)


@pytest.fixture
def ws(tmp_path):
    return make_good_workspace(tmp_path / "my ws")


def drop(ws, *names):
    inbox = ws / "literature" / "inbox"
    for n in names:
        make_pdf(inbox / n, ["placeholder"])
    return inbox


def run(ws, **kw):
    return import_papers.run_import(ws, "stroke thrombolysis outcome", converter=fake_converter, fetch=fake_fetch, **kw)


def test_import_by_doi(ws):
    drop(ws, "thrombo.pdf")
    s = run(ws)
    assert s["query_id"] == "Q-004" and [i["id"] for i in s["imported"]] == ["S-003"]
    ft = ws / "literature" / "fulltext"
    assert (ft / "S-003.pdf").exists() and not (ws / "literature" / "inbox" / "thrombo.pdf").exists()
    md = (ft / "S-003.md").read_text(encoding="utf-8")
    assert "<!-- page 1 -->" in md and "<!-- page 2 -->" in md and "OR 1.32" in md
    rec = rw_io.read_jsonl(ws / P["records"])[-1]
    assert rec["doi"] == "10.1000/s009" and rec["sources"] == ["google_scholar"] and rec["query_ids"] == ["Q-004"]
    assert rec["fulltext"] == {"pdf": "literature/fulltext/S-003.pdf", "md": "literature/fulltext/S-003.md",
                               "md_source": "extracted", "pages": 2, "scanned": False}
    log = rw_io.read_csv(ws / P["search_log"])[-1]
    assert (log["source"], log["count"], log["query"]) == ("google_scholar", "1", "stroke thrombolysis outcome")
    scr = rw_io.read_csv(ws / P["screening"])[-1]
    assert (scr["id"], scr["stage"], scr["decision"], scr["reviewer"]) == ("S-003", "title-abstract", "include", "user")
    assert validate.validate_workspace(ws) == []
    assert trace.trace(ws).ok


def test_import_by_title_when_no_doi(ws):
    drop(ws, "notitle.pdf")
    s = run(ws)
    assert s["imported"][0]["method"] == "title" and s["imported"][0]["doi"] == "10.1000/g5"


def test_ambiguous_title_stays_in_inbox(ws):
    drop(ws, "ambiguous.pdf")
    s = run(ws)
    assert s["imported"] == [] and s["unidentified"][0]["file"] == "ambiguous.pdf"
    assert (ws / "literature" / "inbox" / "ambiguous.pdf").exists()


def test_existing_paper_gets_fulltext(ws):
    drop(ws, "old.pdf")
    s = run(ws)
    assert s["imported"][0]["id"] == "S-001"
    rec = [r for r in rw_io.read_jsonl(ws / P["records"]) if r["id"] == "S-001"][0]
    assert "Q-004" in rec["query_ids"] and rec["fulltext"]["pdf"] == "literature/fulltext/S-001.pdf"


def test_user_md_needs_pdf_and_is_marked(ws):
    inbox = ws / "literature" / "inbox"
    inbox.mkdir(parents=True)
    (inbox / "lonely.md").write_text("# Some paper\n", encoding="utf-8")
    with pytest.raises(ValueError, match="lonely.md"):
        run(ws)
    (inbox / "lonely.md").unlink()
    drop(ws, "mine.pdf")
    (inbox / "mine.md").write_text("# Atrial fibrillation and onset to door time in acute stroke\n\nAI text",
                                   encoding="utf-8")
    s = run(ws)
    sid = s["imported"][0]["id"]
    rec = [r for r in rw_io.read_jsonl(ws / P["records"]) if r["id"] == sid][0]
    assert rec["fulltext"]["md_source"] == "user-ai"
    assert "AI text" in (ws / "literature" / "fulltext" / f"{sid}.md").read_text(encoding="utf-8")


def test_scanned_pdf_needs_doi(ws):
    drop(ws, "scan.pdf")
    assert run(ws)["unidentified"][0]["file"] == "scan.pdf"
    s = run(ws, doi_map={"scan.pdf": "10.1000/s009"})
    sid = s["imported"][0]["id"]
    rec = [r for r in rw_io.read_jsonl(ws / P["records"]) if r["id"] == sid][0]
    assert rec["fulltext"]["scanned"] is True and rec["fulltext"]["md"] is None
    assert s["scanned"] == [sid]


def test_empty_inbox(ws):
    with pytest.raises(ValueError, match="inbox"):
        run(ws)


def test_network_error_keeps_file(ws):
    drop(ws, "thrombo.pdf")

    def down(url, params=None, headers=None):
        raise net.RetrievalError("offline")
    s = import_papers.run_import(ws, "q", converter=fake_converter, fetch=down)
    assert s["errors"][0]["file"] == "thrombo.pdf" and (ws / "literature" / "inbox" / "thrombo.pdf").exists()


def test_real_pdf_extraction(tmp_path):
    pdf = make_pdf(tmp_path / "real.pdf", [f"{NEW_TITLE}\ndoi:10.1000/S009", "Results page two"])
    pages = import_papers.get_converter()(pdf)
    assert len(pages) == 2 and "10.1000/S009" in pages[0] and "page two" in pages[1]
    assert import_papers.find_doi(pages[0]) == "10.1000/s009"
    assert import_papers.guess_title(pages[0]) == NEW_TITLE


def test_arxiv_id_becomes_doi():
    text = "Provided proper attribution is provided, Google hereby grants permission to\narXiv:1706.03762v7 [cs.CL]"
    assert import_papers.find_doi(text) == "10.48550/arxiv.1706.03762"


def test_title_candidates_skip_license_lines():
    text = ("Provided proper attribution is provided, Google hereby grants permission to reproduce\n"
            "Attention Is All You Need\nAshish Vaswani Google Brain")
    assert "Attention Is All You Need" in import_papers.guess_titles(text)
    assert import_papers.guess_titles(text)[0] != text.splitlines()[0]


def test_identify_tries_several_title_lines():
    calls = []

    def fetch(url, params=None, headers=None):
        calls.append(params["search"])
        if params["search"] == "Attention Is All You Need":
            return {"results": [{"id": "W1", "title": "Attention Is All You Need", "publication_year": 2017,
                                 "doi": "https://doi.org/10.48550/arxiv.1706.03762"}]}
        return {"results": []}
    meta, how = import_papers.identify(None, ["Some Other Long Header Line Here", "Attention Is All You Need"], fetch)
    assert how == "title" and meta["year"] == 2017 and len(calls) == 2


DATACITE = {"data": {"attributes": {"titles": [{"title": "Attention Is All You Need"}], "publicationYear": 2017,
                                    "creators": [{"name": "Vaswani, Ashish"}], "publisher": "arXiv",
                                    "url": "https://arxiv.org/abs/1706.03762"}}}


def datacite_only(url, params=None, headers=None):
    if "api.datacite.org/dois/10.48550/arxiv.1706.03762" in url:
        return DATACITE
    raise net.NotFound(url)


def test_arxiv_doi_resolved_via_datacite():
    meta, how = import_papers.identify("10.48550/arxiv.1706.03762", [], datacite_only)
    assert how == "doi" and meta["title"] == "Attention Is All You Need" and meta["year"] == 2017
    assert meta["doi"] == "10.48550/arxiv.1706.03762" and meta["authors"] == ["Vaswani, Ashish"]
