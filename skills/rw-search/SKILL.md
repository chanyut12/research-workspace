---
name: rw-search
description: Run logged literature searches for a research-workbench workspace, either scoping searches for the research questions or literature checks (supporting and contradicting) for a hypothesis. Use when the user wants to search papers, find literature for a hypothesis, or check whether an expert's observation is already known.
argument-hint: "[RQ-n | H-nnn] [scoping|supporting|contradicting|both]"
---

# rw-search

`$S` = `${CLAUDE_SKILL_DIR}/../../scripts`

1. Pick the target and purpose from `$ARGUMENTS`, or ask:
   - **Scoping** (RQ-level): needs G1 approved. If the stage is PROTOCOL_APPROVED, first run `sh "$S/rw" rw_state.py advance LITERATURE --reason "start searching"`.
   - **Literature check for H-nnn**: allowed at any stage. Purpose `both`, or one `supporting` and one `contradicting` search. A hypothesis from the literature needs at least a `contradicting` search.
2. Dispatch one discovery-agent per source in parallel, using the sources from `protocol/protocol.yaml`, with a task packet that names purpose, `for`, and a query budget.
3. When the agents return, run `sh "$S/rw" dedupe.py merge` and `sh "$S/rw" validate.py`. Report the Q-IDs, hit counts, and new/merged records.
4. Any search that failed (`status=error` in `literature/search-log.csv`): tell the user and stop. Never substitute papers from memory.
5. Literature check: add the successful Q-IDs to that hypothesis's `literature_checks` in `synthesis/hypotheses.yaml`, then run `sh "$S/rw" trace.py` and confirm that H-ID no longer has a literature-check warning.
   - Zero hits is a valid result. Tell the user it may be a research gap.
6. Next: `/rw-evidence` to screen new records.
