---
name: rw-evidence
description: Screen literature records and extract source-anchored evidence in a research-workbench workspace, then verify the evidence independently. Use after searches, when the user adds full-text PDFs, or asks to read or screen papers.
---

# rw-evidence

`$S` = `${CLAUDE_SKILL_DIR}/../../scripts`

1. **Title/abstract screening.** Find records in `literature/records.jsonl` with no row in `literature/screening.csv`. Dispatch evidence-analyst (`mode: screen`, stage title-abstract) in parallel batches of about 20 S-IDs.
2. Show the user every `needs-human` row (ID, title, reason) and record their decision as a new screening row with `reviewer: user`.
3. **Full text.** Records imported with `/rw-search import` already have `literature/fulltext/<S-ID>.pdf` and `.md`. For other includes, ask the user to download the PDFs into `literature/inbox/` and run `/rw-search import` again; the DOI matches the existing S-ID. Screen at the full-text stage. A missing file means `awaiting-retrieval`, never exclude.
4. **Extraction.** Dispatch evidence-analyst (`mode: extract`) for the full-text includes, at most 5 papers per agent, in parallel.
5. **Verification.** Dispatch verification-agent (`mode: evidence`) on the new E-IDs. It checks against the PDF pages; this is mandatory for papers whose `fulltext.md_source` is `user-ai`. Report the counts of verified, weaken, rejected and human-review.
6. Run `sh "$S/rw" validate.py` and `sh "$S/rw" trace.py`.
7. When evidence covers the research questions, suggest `/rw-synthesize`.

Counts for a PRISMA-style flow come only from `screening.csv` and `dedupe-log.csv`, never estimated.
