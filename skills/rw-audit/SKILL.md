---
name: rw-audit
description: Audit a research-workbench report before release, covering DOI verification, evidence-chain trace, open must-fix comments and independent claim-by-claim review. Use when the report draft is written or the user asks whether the work is ready to submit.
---

# rw-audit

`$S` = `${CLAUDE_SKILL_DIR}/../../scripts`

1. Run `python3 "$S/verify_doi.py" --scope cited`. Exit 2 means Crossref was unreachable: tell the user and retry later. Do not mark anything verified by hand.
2. Run `python3 "$S/audit.py" run`. This covers trace errors, DOI problems and open `must` comments.
3. Dispatch verification-agent (`mode: claims`) on all claims in `report/claims.jsonl`.
4. Run `python3 "$S/audit.py" status` and show the user the blocking list in Thai, grouped by:
   - wording too strong (WEAKEN)
   - wrong numbers or source (MISMATCH / NOT_FOUND)
   - human review needed
   - DOI problems
   - open comments
5. Send each fix back to its owner: claims and report text to the main session (Writing in `/rw-orchestrate`), evidence to evidence-analyst, comments via `comments.py resolve`. Then repeat from step 2.
6. When status prints OK, run `python3 "$S/rw_state.py" advance AUDITED --reason "audit clean"`, then ask the user to read the report and run `/rw-approve G4`.
