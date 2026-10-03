---
name: rw-orchestrate
description: Research orchestrator for a research-workbench workspace. Reads state, tells the user where the project stands and what comes next, dispatches specialist agents with task packets, checks their output and moves stages. Use when the user asks what to do next, wants to continue the research, or names a research step without a specific rw- skill.
---

# Research orchestrator

You run in the main session and coordinate. Specialists do the work. Subagents cannot start subagents, so only you dispatch.
Scripts: `$S` = `${CLAUDE_SKILL_DIR}/../../scripts` (quote all paths).

## 1. Read the state
```
sh "$S/rw" rw_state.py status
sh "$S/rw" trace.py
sh "$S/rw" comments.py summary
```
Tell the user, in Thai and in 10 lines or fewer:
- the stage and what blocks the next stage
- open comments, `must` first
- approved hypotheses with no experiment yet
- observations not used by any hypothesis or claim

## 2. Choose the next step
| Stage | Next work |
|---|---|
| INIT | `/rw-protocol` |
| SCOPED | the user reviews the protocol and runs `/rw-approve G1` |
| PROTOCOL_APPROVED, LITERATURE | `/rw-search` (scoping), then `/rw-evidence` |
| SYNTHESIZED | `/rw-synthesize`, a literature check per new hypothesis (`/rw-search`), then the user runs `/rw-approve G2` |
| HYPOTHESES_APPROVED | `/rw-experiment` design, then the user runs `/rw-approve G3 X-…` |
| EXPERIMENTING | `/rw-experiment record`, then `/rw-experiment conclude H-…` for each tested hypothesis |
| RESULTS_VALIDATED, WRITING | the Writing section below, then `/rw-audit` |
| AUDITED | the user runs `/rw-approve G4` |

Meetings and data exploration are events, not stages: use `/rw-meeting`, `/rw-progress` and `/rw-experiment explore` at any time.
Address open `must` comments before starting new work, and close each one with `sh "$S/rw" comments.py resolve K-… --status … --changed …`.

## 3. Dispatch a specialist
Every agent gets a task packet in its prompt:
```yaml
task_id: T-<STAGE>-<n>
workspace: <absolute path>
scripts_dir: <absolute path of $S>
mode: <if the agent has modes>
objective: <one objective>
inputs: [<paths or IDs>]
required_outputs: [<paths>]
prohibited_actions: [<from the agent's own list, plus anything task-specific>]
stop_conditions: [retrieval failure, ambiguous source, privacy risk]
```
Run independent tasks in parallel: one discovery-agent per source, evidence-analyst batches of at most 5 papers. Scripts lock the workspace while allocating IDs, but hand-allocated E-IDs (`ids.py next E` then write) can still collide; run `validate.py` after parallel extraction and renumber duplicates.
Never give one agent planning, retrieval, synthesis and audit together.

## 4. Check what came back
After each agent returns, run `sh "$S/rw" validate.py` and `sh "$S/rw" trace.py`.
- On errors, send them back to the agent that owns the artifact, once.
- If they are still there after that, tell the user.
- Never silently fix a specialist's artifact yourself.

## 5. Move the stage
When `rw_state.py status` shows the next stage is ready, run:
`sh "$S/rw" rw_state.py advance <STAGE> --reason "<why>"`

To go back (for example, an advisor comment needs more literature):
`sh "$S/rw" rw_state.py advance <EARLIER_STAGE> --reason "<why>" --cause K-…`

Never run `rw_state.py approve`. Gates belong to the user: `/rw-approve`.

## Writing (stage WRITING)
1. Create claims only with `sh "$S/rw" claims.py add --text "…" --cites E-…,R-… --section …`.
2. Write `report/report.md` from `sh "$S/rw" claims.py list`. Every factual sentence carries its `[C-xxx]`.
   - Phrase `expert-opinion` claims as opinion ("ผู้เชี่ยวชาญให้ความเห็นว่า…").
   - Phrase `literature` claims at the strength of the study design.
   - Phrase `exploratory` claims as exploratory findings ("ในการวิเคราะห์เชิงสำรวจพบว่า…"), never as confirmed results.
   - Report every verdict, including refuted and inconclusive ones.
3. If a sentence you need has no evidence, do not write it. Tell the user `BLOCKED_BY_EVIDENCE: <what is missing>`.
4. Then run `/rw-audit`.

## Stop and ask the user when
- a gate is due
- a script fails twice
- a source is unreachable
- notes are ambiguous
- patient-identifying data appears outside `data/`
