---
name: rw-experiment
description: Explore data, design pre-registered ML experiments for approved hypotheses, record every run and result, and conclude hypotheses (supported/refuted/inconclusive) in a research-workbench workspace. Use when the user does EDA or quick model trials, wants to plan an experiment, has run training/evaluation code (scripts or notebooks), or wants to conclude a hypothesis.
argument-hint: "explore | design H-nnn | record X-nnn | conclude H-nnn"
---

# rw-experiment

`$S` = `${CLAUDE_SKILL_DIR}/../../scripts`

## explore
Data exploration (EDA, quick baselines, feature checks) at any stage, with no hypothesis or gate needed.
1. Create it: `sh "$S/rw" experiment.py new --kind exploratory --objective "…" --dataset-name … --dataset-version … --dataset-path data/…`
2. After the user runs their notebook or script, dispatch experiment-agent (`mode: record`) to log runs and results. Any metric name is allowed here.
3. Exploratory results may seed hypotheses (origin `data-exploration`, `based_on: [R-…]`), but cannot test them, and claims citing them are labeled `exploratory`.
4. A confirmatory test of a data-exploration hypothesis must use held-out or new data; `trace.py` warns when it reuses the same dataset.

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
4. Then conclude each tested hypothesis (below). When all approved experiments have results: `sh "$S/rw" experiment.py done X-…`, then `sh "$S/rw" rw_state.py advance RESULTS_VALIDATED --reason "results recorded"`.

## conclude H-nnn
1. Read the hypothesis, its confirmatory results (`sh "$S/rw" trace.py`), the experiment's analysis plan, and the evidence it rests on.
2. Propose a verdict to the user, judged against the pre-registered primary metric and analysis plan, not against whichever number looks best:
   - `supported`, `refuted` or `inconclusive`
   - the R-IDs it rests on, and the E/O-IDs it agrees or disagrees with
   - a 1–3 sentence rationale

   A refuted or inconclusive result is a finding: say so plainly and keep it.
3. After the user agrees, run `sh "$S/rw" hypotheses.py verdict H-… --outcome … --results R-…,R-… --compare E-…,O-… --rationale "…"`.
4. Stage WRITING is blocked until every hypothesis with confirmatory results has a verdict.
