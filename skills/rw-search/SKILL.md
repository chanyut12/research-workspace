---
name: rw-search
description: Bring literature into a research-workbench workspace, either by importing papers the user found and downloaded (Google Scholar PDFs in literature/inbox/) or by running logged API searches, for the research questions or as literature checks (supporting and contradicting) for a hypothesis. Use when the user has downloaded papers, wants to search papers, or wants to check whether a hypothesis or an expert's observation is already known.
argument-hint: "import | [RQ-n | H-nnn] [scoping|supporting|contradicting|both]"
---

# rw-search

`$S` = `${CLAUDE_SKILL_DIR}/../../scripts`

## import (the user's own Google Scholar search)
The user searches Google Scholar, downloads PDFs and puts them in `literature/inbox/`. They do not need to convert them.
1. Ask for the exact query they typed in Scholar, plus purpose and target (`--for RQ-1` or `H-…`) if this is a hypothesis check.
2. Run `sh "$S/rw" import_papers.py --query "<query>" [--purpose …] [--for …]`.
   - Each PDF is converted to `literature/fulltext/<S-ID>.md` with `<!-- page N -->` markers. This is text extraction, not AI rewriting.
   - The paper is identified by DOI or arXiv ID (Crossref, OpenAlex, DataCite) or by its title (OpenAlex).
   - It is merged into `records.jsonl` and screened `include` at title/abstract with `reviewer: user`, because the user chose it.
3. Show the user the result:
   - UNIDENTIFIED files: ask for the DOI and re-run with `--doi "<file>=<doi>"`. Never guess a DOI.
   - DUPLICATE files: the paper already has a full text; the file stays in the inbox.
   - Scanned PDFs: no text could be extracted; their evidence needs the user or OCR.
4. If the user insists on their own AI-made `.md`, it must sit next to its PDF with the same name. It is then marked `md_source: user-ai`, and every evidence record from it must be verified against the PDF.
5. Next: `/rw-evidence` (full-text screening and extraction can start right away).

## API search (OpenAlex / Crossref / Semantic Scholar)
1. Pick the target and purpose from `$ARGUMENTS`, or ask:
   - **Scoping** (RQ-level): needs G1 approved. If the stage is PROTOCOL_APPROVED, first run `sh "$S/rw" rw_state.py advance LITERATURE --reason "start searching"`.
   - **Literature check for H-nnn**: allowed at any stage. Purpose `both`, or one `supporting` and one `contradicting` search. A hypothesis from the literature needs at least a `contradicting` search.
2. Dispatch one discovery-agent per source in parallel, using the sources from `protocol/protocol.yaml`, with a task packet that names purpose, `for`, and a query budget.
3. When the agents return, run `sh "$S/rw" dedupe.py merge` and `sh "$S/rw" validate.py`. Report the Q-IDs, hit counts, and new/merged records.
4. Any search that failed (`status=error` in `literature/search-log.csv`): tell the user and stop. Never substitute papers from memory.
5. Literature check: add the successful Q-IDs to that hypothesis's `literature_checks` in `synthesis/hypotheses.yaml`, then run `sh "$S/rw" trace.py` and confirm that H-ID no longer has a literature-check warning.
   - Zero hits is a valid result. Tell the user it may be a research gap.
6. Next: `/rw-evidence` to screen new records.
