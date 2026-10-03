"""Merge search candidates into literature/records.jsonl with stable S-IDs and provenance."""
from __future__ import annotations

import argparse
import re
import unicodedata
from pathlib import Path

import ids
import rw_io

P = rw_io.PATHS
DOI_PREFIXES = ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/", "doi:")


def normalize_doi(s) -> str | None:
    if not s:
        return None
    s = str(s).strip().lower()
    for p in DOI_PREFIXES:
        if s.startswith(p):
            s = s[len(p):]
    s = s.strip()
    return s if s.startswith("10.") else None


def normalize_title(s) -> str:
    s = unicodedata.normalize("NFKD", s or "").lower()
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^\w]+", " ", s).split())


def keys_for(c) -> list[tuple]:
    keys = []
    doi = normalize_doi(c.get("doi"))
    if doi:
        keys.append(("doi", doi))
    for k in ("arxiv", "pmid"):
        v = (c.get("identifiers") or {}).get(k)
        if v:
            keys.append((k, str(v).lower()))
    t = normalize_title(c.get("title"))
    if t:
        keys.append(("title", t, c.get("year")))
    return keys


def _find(index, cand):
    cdoi = normalize_doi(cand.get("doi"))
    for key in keys_for(cand):
        rec = index.get(key)
        if rec is None:
            continue
        rdoi = normalize_doi(rec.get("doi"))
        if key[0] == "title" and cdoi and rdoi and cdoi != rdoi:
            continue  # same title but different DOIs: distinct works
        return rec, key
    return None, None


def _to_record(cand, rid) -> dict:
    return {"id": rid, "title": cand["title"].strip(), "year": cand.get("year"),
            "doi": normalize_doi(cand.get("doi")),
            "identifiers": {k: str(v) for k, v in (cand.get("identifiers") or {}).items() if v},
            "sources": [cand["source"]], "query_ids": [cand["query_id"]], "abstract": cand.get("abstract"),
            "authors": cand.get("authors") or [], "venue": cand.get("venue"), "url": cand.get("url")}


def _merge_into(rec, cand) -> None:
    for field, val in (("sources", cand["source"]), ("query_ids", cand["query_id"])):
        if val not in rec[field]:
            rec[field].append(val)
    for k, v in (cand.get("identifiers") or {}).items():
        if v:
            rec["identifiers"].setdefault(k, str(v))
    if not rec.get("doi") and normalize_doi(cand.get("doi")):
        rec["doi"] = normalize_doi(cand.get("doi"))
    for f in ("abstract", "venue", "url", "year"):
        if not rec.get(f) and cand.get(f):
            rec[f] = cand[f]
    if not rec.get("authors") and cand.get("authors"):
        rec["authors"] = cand["authors"]


def merge_candidates(ws) -> dict:
    with rw_io.workspace_lock(ws):  # searches append candidates under the same lock
        return _merge_candidates(Path(ws))


def _merge_candidates(ws: Path) -> dict:
    records = rw_io.read_jsonl(ws / P["records"])
    cands = rw_io.read_jsonl(ws / P["candidates"])
    index = {}
    for r in records:
        for k in keys_for(r):
            index.setdefault(k, r)
    next_n = ids.max_num([r["id"] for r in records]) + 1
    stats = {"new": 0, "merged": 0, "skipped": 0}
    now = rw_io.now_iso()
    for cand in cands:
        if not (cand.get("title") or "").strip():
            stats["skipped"] += 1
            continue
        rec, key = _find(index, cand)
        if rec is None:
            rec = _to_record(cand, f"S-{next_n:03d}")
            next_n += 1
            records.append(rec)
            action, key = "new", keys_for(cand)[0]
        else:
            _merge_into(rec, cand)
            action = "merged"
        for k in keys_for(rec):
            index.setdefault(k, rec)
        stats[action] += 1
        rw_io.append_csv(ws / P["dedupe_log"], {"timestamp": now, "query_id": cand.get("query_id"),
                                                "title": cand["title"], "action": action, "record_id": rec["id"],
                                                "key": ":".join(str(x) for x in key)}, rw_io.DEDUPE_LOG_FIELDS)
    if cands:
        rw_io.write_jsonl(ws / P["records"], records)
        rw_io.write_jsonl(ws / P["candidates"], [])  # raw responses stay in literature/raw/
    return stats


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Merge search candidates into deduplicated records (S-IDs).")
    ap.add_argument("command", choices=["merge"])
    ap.add_argument("--workspace")
    a = ap.parse_args(argv)
    s = merge_candidates(rw_io.resolve_workspace(a.workspace))
    print(f"new={s['new']} merged={s['merged']} skipped={s['skipped']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(rw_io.run_cli(main))
