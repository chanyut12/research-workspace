"""Run one literature search against OpenAlex, Crossref or Semantic Scholar and log it (Q-xxx).

Every execution is recorded in literature/search-log.csv, the raw response is kept in
literature/raw/, and parsed hits are appended to literature/candidates.jsonl for dedupe.py.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import ids
import net
import rw_io
from dedupe import normalize_doi

P = rw_io.PATHS
SOURCES = ("openalex", "crossref", "semantic_scholar")
PURPOSES = ("scoping", "supporting", "contradicting", "both")
FOR_ID = re.compile(r"^((RQ-\d+)|(H-\d{3,}))?$")


def build_request(source, query, from_year=None, to_year=None, limit=50):
    if source == "openalex":
        params = {"search": query, "per-page": min(limit, 200)}
        if from_year and to_year:
            params["filter"] = f"publication_year:{from_year}-{to_year}"
        elif from_year:
            params["filter"] = f"publication_year:>{from_year - 1}"
        elif to_year:
            params["filter"] = f"publication_year:<{to_year + 1}"
        if os.environ.get("RW_MAILTO"):
            params["mailto"] = os.environ["RW_MAILTO"]
        return "https://api.openalex.org/works", params, {}
    if source == "crossref":
        params = {"query.bibliographic": query, "rows": min(limit, 100)}
        f = [x for x in (from_year and f"from-pub-date:{from_year}", to_year and f"until-pub-date:{to_year}") if x]
        if f:
            params["filter"] = ",".join(f)
        return "https://api.crossref.org/works", params, {}
    if source == "semantic_scholar":
        params = {"query": query, "limit": min(limit, 100),
                  "fields": "title,year,externalIds,abstract,authors,venue,url"}
        if from_year or to_year:
            params["year"] = f"{from_year or ''}-{to_year or ''}"
        key = os.environ.get("S2_API_KEY")
        return "https://api.semanticscholar.org/graph/v1/paper/search", params, ({"x-api-key": key} if key else {})
    raise ValueError(f"unknown source {source}; one of {', '.join(SOURCES)}")


def _oa_abstract(inv):
    if not inv:
        return None
    pos = {i: word for word, idxs in inv.items() for i in idxs}
    return " ".join(pos[i] for i in sorted(pos))


def _hit(title, year, doi, identifiers, abstract, authors, venue, url):
    return {"title": (title or "").strip(), "year": year, "doi": normalize_doi(doi),
            "identifiers": {k: str(v) for k, v in identifiers.items() if v}, "abstract": abstract,
            "authors": authors, "venue": venue, "url": url}


def parse(source, payload) -> list[dict]:
    out = []
    if source == "openalex":
        for r in payload.get("results") or []:
            pmid = (r.get("ids") or {}).get("pmid")
            m = re.search(r"(\d+)$", pmid or "")
            loc = (r.get("primary_location") or {}).get("source") or {}
            out.append(_hit(r.get("title") or r.get("display_name"), r.get("publication_year"), r.get("doi"),
                            {"openalex": r.get("id"), "pmid": m.group(1) if m else None},
                            _oa_abstract(r.get("abstract_inverted_index")),
                            [a["author"]["display_name"] for a in r.get("authorships") or [] if a.get("author")],
                            loc.get("display_name"), r.get("doi") or r.get("id")))
    elif source == "crossref":
        for r in (payload.get("message") or {}).get("items") or []:
            parts = ((r.get("issued") or {}).get("date-parts") or [[None]])[0]
            abstract = r.get("abstract")
            if abstract:
                abstract = " ".join(re.sub(r"<[^>]+>", " ", abstract).split())
            out.append(_hit((r.get("title") or [""])[0], parts[0] if parts else None, r.get("DOI"), {}, abstract,
                            [" ".join(x for x in (a.get("given"), a.get("family")) if x) for a in r.get("author") or []],
                            (r.get("container-title") or [None])[0], r.get("URL")))
    elif source == "semantic_scholar":
        for r in payload.get("data") or []:
            ext = r.get("externalIds") or {}
            out.append(_hit(r.get("title"), r.get("year"), ext.get("DOI"),
                            {"s2": r.get("paperId"), "arxiv": ext.get("ArXiv"), "pmid": ext.get("PubMed")},
                            r.get("abstract"), [a.get("name") for a in r.get("authors") or [] if a.get("name")],
                            r.get("venue") or None, r.get("url")))
    else:
        raise ValueError(f"unknown source {source}")
    return out


def parse_datacite(payload) -> dict:
    """DataCite registers DOIs that Crossref does not (arXiv 10.48550, Zenodo, figshare)."""
    a = (payload.get("data") or {}).get("attributes") or {}
    return _hit((a.get("titles") or [{}])[0].get("title"), a.get("publicationYear"), a.get("doi"), {},
                ((a.get("descriptions") or [{}])[0]).get("description"),
                [c.get("name") for c in a.get("creators") or [] if c.get("name")], a.get("publisher"), a.get("url"))


def run_search(ws, source, query, purpose, for_id="", from_year=None, to_year=None, limit=50, fetch=None) -> dict:
    ws = Path(ws)
    if source not in SOURCES:
        raise ValueError(f"unknown source {source}")
    if purpose not in PURPOSES:
        raise ValueError(f"purpose must be one of {', '.join(PURPOSES)}")
    if not FOR_ID.match(for_id or ""):
        raise ValueError("for_id must be empty, RQ-n or H-nnn")
    if for_id and for_id not in ids.existing_ids(ws, for_id.split("-")[0]):
        raise ValueError(f"for_id {for_id} does not exist in this workspace")
    if not query.strip():
        raise ValueError("query is empty")
    if from_year is None and to_year is None:
        dr = (rw_io.read_yaml(ws / P["protocol"]) or {}).get("date_range") or {}
        from_year, to_year = dr.get("from_year"), dr.get("to_year")
    fetch = fetch or net.get_json
    url, params, headers = build_request(source, query, from_year, to_year, limit)
    row = {"purpose": purpose, "for_id": for_id or "", "source": source, "query": query,
           "filters": json.dumps({"from_year": from_year, "to_year": to_year, "limit": limit}),
           "timestamp": rw_io.now_iso(), "count": 0, "status": "ok"}
    try:
        payload, error = fetch(url, params=params, headers=headers), None
    except net.RetrievalError as e:
        payload, error = None, e
    with rw_io.workspace_lock(ws):  # parallel agents: ID allocation and appends happen atomically
        qid = ids.next_id(ws, "Q")
        row["query_id"] = qid
        if error is not None:
            row.update(status="error", raw_file="")
            rw_io.append_csv(ws / P["search_log"], row, rw_io.SEARCH_LOG_FIELDS)
            rw_io.append_jsonl(ws / P["retrieval_errors"], {"query_id": qid, "source": source, "query": query,
                                                            "error": str(error), "timestamp": row["timestamp"]})
        else:
            row["raw_file"] = f"literature/raw/{qid}-{source}.json"
            rw_io.write_json(ws / row["raw_file"], payload)
            hits = parse(source, payload)
            for h in hits:
                rw_io.append_jsonl(ws / P["candidates"], {**h, "source": source, "query_id": qid,
                                                          "retrieved_at": row["timestamp"]})
            row["count"] = len(hits)
            rw_io.append_csv(ws / P["search_log"], row, rw_io.SEARCH_LOG_FIELDS)
    if error is not None:
        raise error
    return row


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Run one logged literature search.")
    ap.add_argument("--workspace")
    ap.add_argument("--source", required=True, choices=SOURCES)
    ap.add_argument("--query", required=True)
    ap.add_argument("--purpose", required=True, choices=PURPOSES)
    ap.add_argument("--for", dest="for_id", default="", help="RQ-n or H-nnn this search serves")
    ap.add_argument("--from-year", type=int)
    ap.add_argument("--to-year", type=int)
    ap.add_argument("--limit", type=int, default=50)
    a = ap.parse_args(argv)
    ws = rw_io.resolve_workspace(a.workspace)
    try:
        row = run_search(ws, a.source, a.query, a.purpose, a.for_id, a.from_year, a.to_year, a.limit)
    except net.RetrievalError as e:
        print(f"retrieval failed: {e}\nlogged to literature/retrieval-errors.jsonl. Stop and ask the user; "
              f"do not substitute results from memory.", file=sys.stderr)
        return 2
    print(f"{row['query_id']} {a.source} {a.purpose}: {row['count']} hits → literature/candidates.jsonl "
          f"(run dedupe.py merge next)")
    return 0


if __name__ == "__main__":
    raise SystemExit(rw_io.run_cli(main))
