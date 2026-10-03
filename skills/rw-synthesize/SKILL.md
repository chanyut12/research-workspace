---
name: rw-synthesize
description: Synthesize verified evidence and expert/advisor observations into themes, contradictions and gaps, and propose testable hypotheses in a research-workbench workspace. Use after evidence extraction, after a meeting yields new observations, or when the user asks what hypotheses to test.
---

# rw-synthesize

`$S` = `${CLAUDE_SKILL_DIR}/../../scripts`

1. Run `sh "$S/rw" trace.py`. Make sure there is evidence or observations to work from, and that no evidence is still `pending` verification. If any is, run `/rw-evidence` step 5 first.
2. Dispatch synthesis-agent with a task packet. Inputs: evidence, observations, results, protocol. Outputs: `synthesis/synthesis.md`, `synthesis/hypotheses.yaml`.
3. Show the user the themes, contradictions and each proposed H (statement, origin, based_on).
4. For each proposed H, run a literature check with `/rw-search H-… both` (for a literature-origin H, a `contradicting` search is enough).
5. When the stage is LITERATURE and hypotheses exist, run `sh "$S/rw" rw_state.py advance SYNTHESIZED --reason "hypotheses proposed"`.
6. Run `sh "$S/rw" trace.py`. When no proposed H has a literature-check warning, ask the user to review and run `/rw-approve G2` (or `/rw-approve G2 H-… H-…` for some of them).
