"""Import papers the user found and downloaded (e.g. from Google Scholar) from literature/inbox/.

For every PDF: extract text page by page (no AI rewriting) into Markdown with <!-- page N --> markers,
identify the paper (DOI in the first pages → Crossref/OpenAlex; else title → OpenAlex), merge it into
records.jsonl as an S-ID, and file it as literature/fulltext/<S-ID>.pdf + .md. A .md the user made
(e.g. by asking an AI) is accepted only next to its PDF and is marked md_source=user-ai.
"""
from __future__ import annotations

import argparse
import re
import shutil
import urllib.parse
from difflib import SequenceMatcher
from pathlib import Path

import dedupe
import ids
import net
import rw_io
import search

P = rw_io.PATHS
DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>]+)", re.I)
ARXIV_RE = re.compile(r"arXiv:\s*(\d{4}\.\d{4,5})(v\d+)?", re.I)
NOT_TITLE = re.compile(r"(doi|https?:|©|copyright|journal|vol\.|issn|received|accepted|published|licen[cs]e|"
                       r"permission|grants?|attribution|arxiv|preprint|proceedings|conference|@)", re.I)
MAX_TITLE_TRIES = 4
MIN_CHARS_PER_PAGE = 25  # image-only (scanned) PDFs yield almost no text on every page
TITLE_MATCH = 0.9


def get_converter():
    """Return pdf_path -> list of page texts. Prefers pymupdf4llm (better tables, AGPL), else pypdf (BSD)."""
    try:
        import pymupdf4llm

        def convert(path):
            return [c.get("text", "") for c in pymupdf4llm.to_markdown(str(path), page_chunks=True)]
        return convert
    except ImportError:
        pass
    try:
        from pypdf import PdfReader

        def convert(path):
            return [(page.extract_text() or "") for page in PdfReader(str(path)).pages]
        return convert
    except ImportError:
        raise ValueError("no PDF reader installed: ~/.research-workbench/venv/bin/pip install pypdf "
                         "(or pymupdf4llm for better tables; AGPL license)") from None


def find_doi(text) -> str | None:
    m = DOI_RE.search(text or "")
    if m:
        return dedupe.normalize_doi(m.group(1).rstrip(".,;)]}'"))
    a = ARXIV_RE.search(text or "")  # arXiv PDFs carry an arXiv ID, not a DOI; DataCite DOI 10.48550
    return f"10.48550/arxiv.{a.group(1)}" if a else None


def guess_titles(text) -> list[str]:
    """Lines near the top that look like a title, best first (front matter and license lines skipped)."""
    out = []
    for line in (text or "").splitlines()[:60]:
        s = line.strip().lstrip("#").strip()
        if 3 <= len(s.split()) <= 40 and 15 <= len(s) <= 300 and not NOT_TITLE.search(s) and s not in out:
            out.append(s)
    return out[:MAX_TITLE_TRIES]


def guess_title(text) -> str | None:
    titles = guess_titles(text)
    return titles[0] if titles else None


def to_markdown(pages, title) -> str:
    body = "".join(f"<!-- page {i} -->\n{text.strip()}\n\n" for i, text in enumerate(pages, 1))
    return f"# {title}\n\n<!-- extracted by research-workbench from the PDF; text is not rewritten -->\n\n{body}"


def _by_doi(doi, fetch):
    quoted = urllib.parse.quote(doi, safe="/()")
    try:
        msg = fetch("https://api.crossref.org/works/" + quoted, params=None, headers=None).get("message") or {}
        return search.parse("crossref", {"message": {"items": [msg]}})[0]
    except net.NotFound:
        pass
    try:
        work = fetch("https://api.openalex.org/works/doi:" + quoted, params=None, headers=None)
        return search.parse("openalex", {"results": [work]})[0]
    except net.NotFound:
        pass
    try:
        meta = search.parse_datacite(fetch("https://api.datacite.org/dois/" + quoted, params=None, headers=None))
        return {**meta, "doi": meta.get("doi") or doi}
    except net.NotFound:
        return None


def _by_title(title, fetch):
    payload = fetch("https://api.openalex.org/works", params={"search": title, "per-page": 5}, headers=None)
    want = dedupe.normalize_title(title)
    scored = sorted(((SequenceMatcher(None, want, dedupe.normalize_title(h["title"])).ratio(), h)
                     for h in search.parse("openalex", payload)), key=lambda x: -x[0])
    good = [h for score, h in scored if score >= TITLE_MATCH]
    if len(good) == 1 or (good and len({dedupe.normalize_doi(h.get("doi")) for h in good}) == 1):
        return good[0]
    return None


def identify(doi, titles, fetch):
    """Return (metadata, method) or (None, reason). `titles` are candidate title lines, best first."""
    if doi:
        meta = _by_doi(doi, fetch)
        if meta:
            return meta, "doi"
    for title in titles or []:
        meta = _by_title(title, fetch)
        if meta:
            return meta, "title"
    if titles:
        return None, f"no single OpenAlex match for title lines {titles!r} — pass --doi FILE=DOI"
    return None, "no DOI or title found in the text (scanned PDF?) — pass --doi FILE=DOI"


def run_import(ws, query, purpose="scoping", for_id="", doi_map=None, fetch=None, converter=None,
               source="google_scholar") -> dict:
    ws = Path(ws)
    inbox = ws / P["inbox"]
    pdfs = sorted(p for p in inbox.iterdir() if p.suffix.lower() == ".pdf") if inbox.exists() else []
    mds = {p.stem: p for p in inbox.glob("*.md")} if inbox.exists() else {}
    lonely = sorted(p.name for stem, p in mds.items() if stem not in {q.stem for q in pdfs})
    if lonely:
        raise ValueError(f"a .md needs its PDF next to it (same name) so evidence can be checked against the "
                         f"original: {', '.join(lonely)}")
    if not pdfs:
        raise ValueError("literature/inbox has no PDF files; put the papers you downloaded there first")
    if purpose not in search.PURPOSES:
        raise ValueError(f"purpose must be one of {', '.join(search.PURPOSES)}")
    if not search.FOR_ID.match(for_id or ""):
        raise ValueError("for_id must be empty, RQ-n or H-nnn")
    if not (query or "").strip():
        raise ValueError("--query is required: the search you typed in Google Scholar (for the search log)")
    fetch, convert = fetch or net.get_json, converter or get_converter()
    doi_map = {k: dedupe.normalize_doi(v) for k, v in (doi_map or {}).items()}
    summary = {"imported": [], "unidentified": [], "duplicates": [], "scanned": [], "errors": []}
    prepared = []
    for pdf in pdfs:
        try:
            pages = convert(pdf)
        except Exception as e:  # damaged or encrypted PDF: keep it in the inbox and report
            summary["errors"].append({"file": pdf.name, "error": f"cannot read PDF: {e}"})
            continue
        scanned = sum(len(t.strip()) for t in pages) < MIN_CHARS_PER_PAGE * max(len(pages), 1)
        user_md = mds.get(pdf.stem)
        md_text = user_md.read_text(encoding="utf-8") if user_md else None
        first = "\n".join(pages[:2]).strip() or (md_text or "")[:6000]
        try:
            meta, how = identify(doi_map.get(pdf.name) or find_doi(first), guess_titles(first), fetch)
        except net.RetrievalError as e:
            summary["errors"].append({"file": pdf.name, "error": str(e)})
            continue
        if meta is None:
            summary["unidentified"].append({"file": pdf.name, "reason": how})
            continue
        if md_text is None and not scanned:
            md_text = to_markdown(pages, meta["title"])
        prepared.append({"pdf": pdf, "user_md": user_md, "md": md_text, "pages": len(pages), "scanned": scanned,
                         "meta": meta, "method": how})
    with rw_io.workspace_lock(ws):
        qid = ids.next_id(ws, "Q")
        now = rw_io.now_iso()
        for item in prepared:
            rw_io.append_jsonl(ws / P["candidates"], {**item["meta"], "source": source, "query_id": qid,
                                                      "retrieved_at": now})
        _, assigned = dedupe._merge_candidates(ws) if prepared else ({}, [])
        assigned = assigned[len(assigned) - len(prepared):]
        records = rw_io.read_jsonl(ws / P["records"])
        by_id = {r["id"]: r for r in records}
        screened = {row.get("id") for row in rw_io.read_csv(ws / P["screening"])}
        protocol_version = rw_io.read_json(ws / P["state"]).get("protocol_version", 0)
        ft = ws / P["fulltext"]
        ft.mkdir(parents=True, exist_ok=True)
        for item, sid in zip(prepared, assigned):
            if (ft / f"{sid}.pdf").exists():
                summary["duplicates"].append({"file": item["pdf"].name, "id": sid})
                continue
            shutil.move(str(item["pdf"]), ft / f"{sid}.pdf")
            md_rel = None
            if item["md"] is not None:
                md_rel = f"{P['fulltext']}/{sid}.md"
                (ws / md_rel).write_text(item["md"], encoding="utf-8")
                if item["user_md"]:
                    item["user_md"].unlink()
            by_id[sid]["fulltext"] = {"pdf": f"{P['fulltext']}/{sid}.pdf", "md": md_rel,
                                      "md_source": None if md_rel is None else ("user-ai" if item["user_md"] else "extracted"),
                                      "pages": item["pages"], "scanned": item["scanned"]}
            if sid not in screened:  # the user picked this paper: that is a title/abstract decision
                rw_io.append_csv(ws / P["screening"], {
                    "id": sid, "stage": "title-abstract", "decision": "include", "reason_code": "USER-SELECTED",
                    "confidence": "1", "reviewer": "user", "timestamp": now,
                    "protocol_version": protocol_version}, rw_io.SCREENING_FIELDS)
            if item["scanned"]:
                summary["scanned"].append(sid)
            summary["imported"].append({"file": item["pdf"].name, "id": sid, "doi": by_id[sid].get("doi"),
                                        "method": item["method"], "title": by_id[sid]["title"]})
        rw_io.write_jsonl(ws / P["records"], records)
        manifest = f"literature/raw/{qid}-{source}.json"
        rw_io.write_json(ws / manifest, {"query": query, "source": source, "imported": summary["imported"],
                                         "unidentified": summary["unidentified"], "errors": summary["errors"]})
        rw_io.append_csv(ws / P["search_log"], {
            "query_id": qid, "purpose": purpose, "for_id": for_id or "", "source": source, "query": query,
            "filters": '{"method": "user download"}', "timestamp": now,
            "count": len(summary["imported"]) + len(summary["duplicates"]), "raw_file": manifest, "status": "ok"},
            rw_io.SEARCH_LOG_FIELDS)
    summary["query_id"] = qid
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Import downloaded paper PDFs from literature/inbox/.")
    ap.add_argument("--workspace")
    ap.add_argument("--query", required=True, help="what you searched in Google Scholar (logged)")
    ap.add_argument("--purpose", default="scoping", choices=search.PURPOSES)
    ap.add_argument("--for", dest="for_id", default="")
    ap.add_argument("--source", default="google_scholar", choices=["google_scholar", "manual"])
    ap.add_argument("--doi", action="append", default=[], metavar="FILE=DOI",
                    help="give the DOI of a PDF that cannot be identified (repeatable)")
    a = ap.parse_args(argv)
    doi_map = dict(x.split("=", 1) for x in a.doi if "=" in x)
    s = run_import(rw_io.resolve_workspace(a.workspace), a.query, a.purpose, a.for_id, doi_map, source=a.source)
    print(f"{s['query_id']}: imported {len(s['imported'])}")
    for i in s["imported"]:
        print(f"  {i['id']}  {i['file']}  ({i['method']}) {i['title']}")
    for d in s["duplicates"]:
        print(f"  DUPLICATE {d['file']}: {d['id']} already has a full text; file left in inbox")
    for u in s["unidentified"]:
        print(f"  UNIDENTIFIED {u['file']}: {u['reason']}")
    for e in s["errors"]:
        print(f"  ERROR {e['file']}: {e['error']}")
    if s["scanned"]:
        print(f"  scanned PDFs without text (need human reading/OCR): {', '.join(s['scanned'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(rw_io.run_cli(main))
