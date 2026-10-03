---
name: rw-protocol
description: Draft or amend the research protocol (research questions, scope, eligibility criteria, sources, date range) of a research-workbench workspace with the protocol-designer agent. Use at the start of a project or when the scope must change.
---

# rw-protocol

`$S` = `${CLAUDE_SKILL_DIR}/../../scripts`

1. Run `python3 "$S/rw_state.py" status`.
2. If G1 is already approved, this is an amendment:
   - Ask the user what changes and why.
   - Dispatch protocol-designer to write `protocol/amendments/<date>-<slug>.yaml` with `protocol_version` + 1.
   - Then tell the user to run `/rw-approve amend <file> --note "<reason>"`.
   - Stop here.
3. Otherwise, interview the user one question at a time:
   - the clinical or ML question
   - population or dataset, predictors or exposure, outcome, time frame
   - review type: scoping by default for a thesis background
   - date range, languages, sources (default: openalex, crossref, semantic_scholar)

   Use PICO/PICOTS for prediction questions and PCC for scoping questions.
4. Dispatch protocol-designer (see `/rw-orchestrate` for the task packet) with the answers.
5. Run `python3 "$S/validate.py"`. Show the protocol to the user as a short Thai summary.
6. Run `python3 "$S/rw_state.py" advance SCOPED --reason "protocol drafted"`.
7. Ask the user to review the protocol and run `/rw-approve G1`.
