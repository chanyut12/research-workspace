"""Verify record DOIs against Crossref: verified / metadata-mismatch / not-found / retracted-check-needed."""
from __future__ import annotations

import argparse
import urllib.parse
from pathlib import Path

import net
import rw_io
import trace
from dedupe import normalize_doi, normalize_title

P = rw_io.PATHS
CROSSREF_WORK = "https://api.crossref.org/works/"
OPENALEX_WORK = "https://api.openalex.org/works/doi:"
FLAG_TYPES = {"retraction", "partial_retraction", "withdrawal", "removal", "expression_of_concern"}


def compare(record, message) -> tuple[str, str]:
    updates = (message.get("updated-by") or []) + (message.get("update-to") or [])
    flagged = sorted({u.get("type") for u in updates if u.get("type") in FLAG_TYPES})
    if flagged:
        return "retracted-check-needed", "Crossref update: " + ", ".join(flagged)
    c_title = (message.get("title") or [""])[0]
    ct, rt = normalize_title(c_title), normalize_title(record.get("title"))
    title_ok = bool(ct and rt) and (ct == rt or ct in rt or rt in ct)
    parts = ((message.get("issued") or {}).get("date-parts") or [[None]])[0]
    cy, ry = (parts[0] if parts else None), record.get("year")
    year_ok = cy is None or ry is None or abs(int(cy) - int(ry)) <= 1  # online vs print year
    if title_ok and year_ok:
        return "verified", ""
    detail = []
    if not title_ok:
        detail.append(f"title differs: Crossref '{c_title}'")
    if not year_ok:
        detail.append(f"year differs: Crossref {cy} vs record {ry}")
    return "metadata-mismatch", "; ".join(detail)


def verify_record(record, fetch=None) -> dict:
    fetch = fetch or net.get_json
    doi = normalize_doi(record.get("doi"))
    base = {"id": record["id"], "doi": doi, "checked_at": rw_io.now_iso()}
    if not doi:
        return {**base, "status": "no-doi", "detail": "record has no DOI"}
    try:
        payload = fetch(CROSSREF_WORK + urllib.parse.quote(doi, safe="/()"), params=None, headers=None)
    except net.NotFound:
        return _verify_in_openalex(record, doi, base, fetch)
    except net.RetrievalError as e:
        return {**base, "status": "error", "detail": str(e)}
    status, detail = compare(record, payload.get("message") or {})
    return {**base, "status": status, "detail": detail}


def _verify_in_openalex(record, doi, base, fetch) -> dict:
    """DOIs registered outside Crossref (DataCite: arXiv, Zenodo, figshare) are 404 there."""
    try:
        work = fetch(OPENALEX_WORK + urllib.parse.quote(doi, safe="/()"), params=None, headers=None)
    except net.NotFound:
        return {**base, "status": "not-found", "detail": "neither Crossref nor OpenAlex knows this DOI"}
    except net.RetrievalError as e:
        return {**base, "status": "error", "detail": str(e)}
    message = {"title": [work.get("title") or work.get("display_name") or ""],
               "issued": {"date-parts": [[work.get("publication_year")]]}}
    status, detail = compare(record, message)
    return {**base, "status": status,
            "detail": "non-Crossref registrar (found in OpenAlex)" if status == "verified" else detail}


def record_ids(ws, scope) -> list[str]:
    g = trace.load_graph(ws)
    if scope == "all":
        return sorted(g["records"])
    if scope == "evidence":
        return sorted({e.get("study_id") for e in g["evidence"].values()} & set(g["records"]))
    cited = {ref for c in g["claims"].values() for ref in c.get("cites", [])}
    cited |= {ref for h in g["hypotheses"].values() for ref in h.get("based_on", [])}
    return sorted({g["evidence"][e].get("study_id") for e in cited if e in g["evidence"]} & set(g["records"]))


def verify_workspace(ws, scope="evidence", fetch=None) -> list[dict]:
    ws = Path(ws)
    records = trace.load_graph(ws)["records"]
    results = []
    for sid in record_ids(ws, scope):
        res = verify_record(records[sid], fetch=fetch)
        rw_io.append_jsonl(ws / P["doi_verification"], res)
        results.append(res)
    return results


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Verify DOIs of records against Crossref.")
    ap.add_argument("--workspace")
    ap.add_argument("--scope", choices=["cited", "evidence", "all"], default="evidence")
    a = ap.parse_args(argv)
    results = verify_workspace(rw_io.resolve_workspace(a.workspace), a.scope)
    for r in results:
        print(f"{r['id']}\t{r['status']}\t{r['doi'] or '-'}\t{r['detail']}")
    print(f"checked {len(results)} record(s)")
    return 2 if any(r["status"] == "error" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(rw_io.run_cli(main))
