---
name: rw-evidence
description: Screen literature records and extract source-anchored evidence in a research-workbench workspace, then verify the evidence independently. Use after searches, when the user adds full-text PDFs, or asks to read or screen papers.
---

# rw-evidence

`$S` = `${CLAUDE_SKILL_DIR}/../../scripts`

1. **Title/abstract screening.** Find records in `literature/records.jsonl` with no row in `literature/screening.csv`. Dispatch evidence-analyst (`mode: screen`, stage title-abstract) in parallel batches of about 20 S-IDs.
2. Show the user every `needs-human` row (ID, title, reason) and record their decision as a new screening row with `reviewer: user`.
3. **Full text.** Ask the user to place PDFs or text for the includes in `literature/fulltext/<S-ID>.pdf`. Screen them at the full-text stage. A missing file means `awaiting-retrieval`, never exclude.
4. **Extraction.** Dispatch evidence-analyst (`mode: extract`) for the full-text includes, at most 5 papers per agent, in parallel.
5. **Verification.** Dispatch verification-agent (`mode: evidence`) on the new E-IDs. Report the counts of verified, weaken, rejected and human-review.
6. Run `python3 "$S/validate.py"` and `python3 "$S/trace.py"`.
7. When evidence covers the research questions, suggest `/rw-synthesize`.

Counts for a PRISMA-style flow come only from `screening.csv` and `dedupe-log.csv`, never estimated.
