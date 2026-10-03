---
name: rw-experiment
description: Design pre-registered ML experiments for approved hypotheses and record every run and result in a research-workbench workspace. Use when the user wants to plan an experiment, has run training/evaluation code, or wants results linked to hypotheses.
argument-hint: "design H-nnn | record X-nnn"
---

# rw-experiment

`$S` = `${CLAUDE_SKILL_DIR}/../../scripts`

## design H-nnn
1. Check that the H is approved at G2 (`sh "$S/rw" rw_state.py status`).
2. If the `ml-model-advisor` or `stroke-research-expert` skills are available, use them to stress-test the split, leakage, metrics and baselines.
3. Dispatch experiment-agent (`mode: design`). It creates `experiments/X-…/spec.yaml` as a draft.
4. Show the spec to the user. Changes are fine until G3, so edit the spec together if needed.
5. Ask the user to run `/rw-approve G3 X-…`. From then on the spec is frozen. When the stage is HYPOTHESES_APPROVED, advance with `sh "$S/rw" rw_state.py advance EXPERIMENTING --reason "X-… approved"`.

## record X-nnn
1. The user's training code lives in the workspace; outputs go to `experiments/X-…/outputs/` (git-ignored).
2. Dispatch experiment-agent (`mode: record`) with the output files. It logs every run, including failed ones, and adds results only for pre-registered metrics.
3. Run `sh "$S/rw" trace.py`. Show the user the new R-IDs with their numbers.
4. When all approved experiments have results: `sh "$S/rw" experiment.py done X-…`, then `sh "$S/rw" rw_state.py advance RESULTS_VALIDATED --reason "results recorded"`.
