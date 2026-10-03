# research-workbench

**An evidence-traceable research workflow for Claude Code.**

research-workbench is a Claude Code plugin that guides a research project from literature review through expert consultation, hypothesis formation, machine-learning experiments and a final report, so that every claim in the report can be traced back to its source. It targets empirical research that combines published evidence with a project's own data, and it was designed around clinical machine-learning work, where hypotheses often originate from clinicians and advisors as much as from papers.

[ภาษาไทย (Thai documentation)](README.th.md)

> **Status: early (v0.2).** The test suite passes (189 tests), the plugin loads and its hooks run inside Claude Code, and paper import was exercised on a real arXiv paper. The workflow has not yet been validated end to end on a full research project. See [Known limitations](#known-limitations).

## Contents

- [Why this exists](#why-this-exists)
- [How it works](#how-it-works)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Commands](#commands)
- [The evidence chain](#the-evidence-chain)
- [Workflow and gates](#workflow-and-gates)
- [Workspace layout](#workspace-layout)
- [Importing papers from Google Scholar](#importing-papers-from-google-scholar)
- [Exploratory and confirmatory experiments](#exploratory-and-confirmatory-experiments)
- [Data handling](#data-handling)
- [Safeguards](#safeguards)
- [Known limitations](#known-limitations)
- [Development](#development)
- [License and acknowledgements](#license-and-acknowledgements)

## Why this exists

Language models are useful research assistants and unreliable record keepers. They can invent citations, alter a number while summarizing, skip a step, or quietly redefine success after seeing results. This plugin does not ask the model to be careful; it removes the opportunity to be careless:

- **Work is exchanged as files with schemas**, not as conversation. Each artifact has an ID, and each ID points to where it came from.
- **Deterministic work is done by code.** ID allocation, validation, de-duplication, DOI checks and evidence-chain checks are Python scripts, not model judgment.
- **Producers and checkers are different agents.** The agent that verifies evidence has no tool for writing files.
- **Humans hold the gates.** Approving a protocol, a hypothesis, an experiment design or a release is something only the user can do.
- **Knowledge comes from two sources.** Papers *and* people (clinicians, advisors) are first-class evidence, and each is labelled as what it is.

## How it works

```
You ──► Skills (/rw-…)            step-by-step procedures, one per stage
          │
          ▼
        Orchestrator              the main Claude session: reads state, dispatches, checks, advances
          │ task packets
          ▼
        Six specialist agents     each isolated, each with a narrow remit and a prohibited-actions list
          │ call
          ▼
        Python scripts            deterministic: state machine, IDs, validation, search, trace, audit
          │ read / write
          ▼
        Workspace files           JSON / JSONL / YAML / CSV / Markdown, one schema per artifact type

        Hooks (always on)         validate every artifact written; block human-only actions
```

| Layer | Role |
|---|---|
| **Skills** (11) | Procedures the model follows for each stage. `rw-approve` is hidden from the model and can only be invoked by the user. |
| **Orchestrator** | Runs in the main session (subagents cannot spawn subagents). Delegates through task packets stating objective, inputs, outputs, prohibited actions and stop conditions, and re-validates what comes back. |
| **Agents** (6) | `protocol-designer`, `discovery-agent`, `evidence-analyst`, `synthesis-agent`, `experiment-agent`, `verification-agent`. |
| **Scripts** | Everything with a right or wrong answer. Always invoked through `scripts/rw`, which selects a Python interpreter that has the required packages. |
| **Hooks** | `hook_guard` runs before writes and shell commands; `hook_validate` runs after writes. |

## Installation

**Requirements:** Claude Code, Python 3.10 or later.

1. **Create a dedicated Python environment** (once). Scripts are launched through `scripts/rw`, which looks for an interpreter with the required packages in this order: `$RW_PYTHON`, `~/.research-workbench/venv`, the plugin's own `.venv`, then `python3` on `PATH`. A dedicated environment therefore works regardless of which project virtual environment is active.

   ```bash
   python3 -m venv ~/.research-workbench/venv
   ~/.research-workbench/venv/bin/pip install pyyaml jsonschema pypdf
   ```

2. **Install the plugin.**

   ```text
   /plugin marketplace add chanyut12/research-workspace
   /plugin install research-workbench@research-workbench
   ```

   To try it from a local checkout instead: `claude --plugin-dir /path/to/research-workbench`.

3. **Optional environment variables.**

   | Variable | Purpose |
   |---|---|
   | `RW_MAILTO` | Your email, sent to OpenAlex and Crossref to use their "polite pool" |
   | `S2_API_KEY` | Semantic Scholar API key (higher rate limits) |
   | `RW_PYTHON` | Path of the Python interpreter that scripts should use |

   Optionally install `pymupdf4llm` for better table extraction from PDFs. It is licensed AGPL, so it is not a default dependency.

Claude Code namespaces plugin skills as `/research-workbench:<skill>`. This document uses the short form `/rw-…` for readability; use the prefixed form if the short one is not recognized.

## Quick start

```text
/rw-init . --title "Stroke outcome prediction"
/rw-orchestrate
```

`/rw-init` creates the workspace in the current folder, new or existing. An existing `CLAUDE.md` or `.gitignore` is appended to, never overwritten. `/rw-orchestrate` reports the current stage, what is blocking the next one, open advisor comments, and the recommended next command. Run it whenever you are unsure what to do next.

A typical first session:

1. `/rw-protocol` — define the research question, scope and eligibility criteria. Review it, then run `/rw-approve G1`.
2. Search Google Scholar yourself, download the PDFs into `literature/inbox/`, then `/rw-search import`.
3. `/rw-evidence` — screen the papers and extract source-anchored evidence.
4. After a consultation or advisor meeting: `/rw-meeting log` to record what was said.
5. `/rw-synthesize` — synthesize, and propose hypotheses.

## Commands

| Command | Purpose |
|---|---|
| `/rw-init` | Create a workspace. |
| `/rw-orchestrate` | Show status and the next step; dispatch specialist agents. |
| `/rw-protocol` | Draft the protocol, or an amendment after G1. |
| `/rw-search` | `import` papers you downloaded, or run logged API searches (OpenAlex, Crossref, Semantic Scholar), including literature checks for a hypothesis. |
| `/rw-evidence` | Screen records, extract evidence with page, section or table anchors, and verify it independently. |
| `/rw-meeting` | `new`, `prep` and `log` expert consultations, advisor reviews and self-notes. |
| `/rw-progress` | Build a progress-review document for an advisor meeting from the artifacts. |
| `/rw-synthesize` | Synthesize evidence and observations; propose hypotheses. |
| `/rw-experiment` | `explore`, `design`, `record` and `conclude`. |
| `/rw-audit` | Verify DOIs, the evidence chain, open comments and every claim before release. |
| `/rw-approve` | **User only.** `G1`, `G2 [H-…]`, `G3 X-…`, `G4`, `amend <file> --note "…"`. |

## The evidence chain

Every artifact has an ID, and every ID refers back to what it rests on.

```text
        E  (paper evidence)  ─┐
        O  (clinician/advisor) ┼─►  H  ─►  X  ─►  R  ─►  C   (claim in the report)
        R  (earlier results)  ─┘    ▲
                                    └── K  (advisor comment; can require changes to H, X, R or C)
```

| ID | Meaning | Must reference |
|---|---|---|
| `RQ-n` | Research question | — |
| `Q-nnn` | A search that was actually run (or an import) | Logged with query, source and timestamp |
| `S-nnn` | A paper or record | Identifier from a database (DOI, arXiv ID, PMID) |
| `E-nnn` | Evidence extracted from a paper | `S` and a page, section, table or figure anchor |
| `M-nnn` | A meeting | Type, date, participant roles |
| `O-nnn` | An observation from a person | `M`, speaker role, whether quoted verbatim or paraphrased, user confirmation |
| `K-nnn` | A comment or action item | `M`, target (an `H`, `X`, `R` or `C`, or general), severity |
| `H-nnn` | A hypothesis | Its origin (`literature`, `expert`, `advisor`, `data-exploration`), at least one `E`, `O` or `R`, and literature checks |
| `X-nnn` | An experiment | An `H` (confirmatory) or none (exploratory) |
| `RUN-nnn` | A run of an experiment, including failed runs | `X` |
| `R-nnn` | A result | `X` and a successful `RUN` |
| `C-nnn` | A claim in the report | One or more `E`, `O` or `R`; its support level is computed, not typed |

`trace.py` enforces the chain. It fails on dangling references, hypotheses without literature checks, unconfirmed observations, results from failed runs, claims whose stated support level does not match their citations, and protocol or experiment specs changed after approval.

Claims carry a computed **support level**: `literature`, `experimental`, `expert-opinion`, `exploratory` or `mixed`. A claim resting only on an observation is `expert-opinion` and must be written as opinion. Exploratory results are never mixed with other evidence in one claim.

## Workflow and gates

```text
INIT → SCOPED ─[G1]→ PROTOCOL_APPROVED → LITERATURE → SYNTHESIZED ─[G2]→ HYPOTHESES_APPROVED
     ─[G3]→ EXPERIMENTING → RESULTS_VALIDATED → WRITING → AUDITED ─[G4]→ RELEASED
```

| Gate | The user approves | Checked by script first |
|---|---|---|
| **G1** | The protocol: questions, criteria, sources | Protocol passes validation |
| **G2** | The hypotheses to test | Each has a real source and literature checks; a literature-origin hypothesis needs a search for contradicting work, others need both supporting and contradicting searches |
| **G3** | An experiment design, before any run | The spec belongs to a G2-approved hypothesis. The spec is frozen afterwards |
| **G4** | Release of the report | Evidence chain intact, audit clean, no open `must` comment |

- The stage machine and gates are code (`rw_state.py`), not model judgment.
- Moving backwards is allowed (for example, an advisor asks for more literature) but requires a reason and the comment that caused it, and is logged in `rw/decision-log.jsonl`.
- Entering `WRITING` requires a recorded verdict for every hypothesis that has confirmatory results.
- Meetings, data exploration and new hypotheses are events, not stages. They can happen at any time.

## Workspace layout

`/rw-init` creates this structure in your research folder. The plugin repository contains no research data.

```text
your-project/
├── CLAUDE.md                 rules for the AI in this project
├── rw/                       state.json, decision-log.jsonl (written only by scripts)
├── protocol/                 protocol.yaml and amendments/
├── literature/
│   ├── inbox/                put downloaded PDFs here
│   ├── fulltext/             <S-ID>.pdf and <S-ID>.md (page-marked text)
│   ├── search-log.csv        every search and import
│   ├── records.jsonl         de-duplicated papers (S)
│   ├── screening.csv         decisions with reason codes
│   └── evidence.jsonl        evidence (E)
├── meetings/                 M-xxx/ (notes), observations.jsonl (O), comments.jsonl (K)
├── synthesis/                synthesis.md, hypotheses.yaml (H, with verdicts)
├── experiments/X-xxx/        spec.yaml, runs.jsonl, results.jsonl
├── progress/                 progress-review documents
├── report/                   claims.jsonl (C), report.md, audit.json
└── data/                     your datasets (git-ignored)
```

## Importing papers from Google Scholar

Google Scholar has no API and prohibits automated access, so the workflow starts from papers you choose yourself:

1. Search Google Scholar as usual and download the PDFs into `literature/inbox/`. No conversion is needed.
2. Run `/rw-search import`. You will be asked for the query you typed, which is recorded in the search log.

For each PDF the importer:

- **Extracts the text with code, not an AI model**, page by page, into Markdown with `<!-- page N -->` markers. Nothing is summarized or rewritten, so numbers and wording match the PDF.
- **Identifies the paper** from a DOI or arXiv ID found in the first pages (Crossref, then OpenAlex, then DataCite), or from the title (OpenAlex, accepted only if the results match a single paper). If it cannot identify a file, it says so and asks for the DOI. It never guesses.
- **Merges it with existing records**, files the PDF and Markdown under its `S-ID`, and records that you selected it at title and abstract screening. Full-text screening still follows the protocol.

The original PDF is always kept, and the verification agent checks evidence against the PDF page itself, not the Markdown copy. If you prefer to supply your own converted `.md`, place it next to the PDF with the same name; it is accepted but marked `md_source: user-ai`, and its evidence must be checked against the PDF. Scanned image PDFs cannot be extracted and are flagged for manual reading.

## Exploratory and confirmatory experiments

Real analysis starts by looking at data, so the workflow separates two kinds of experiment:

| | Exploratory | Confirmatory |
|---|---|---|
| Purpose | EDA, quick baselines, finding patterns | Testing a hypothesis |
| Hypothesis required | No | Yes (approved at G2) |
| Gate | None | G3, before any run |
| Metrics | Any | Pre-registered in the spec; frozen after G3 |
| May seed a hypothesis | Yes (origin `data-exploration`) | — |
| May support a verdict | **No** | Yes |
| In a report | Labelled `exploratory` | Reported as results |

If a confirmatory test reuses the dataset that generated its hypothesis, `trace.py` warns that this is circular and suggests held-out or new data.

Every tested hypothesis must be concluded with a **verdict** — `supported`, `refuted` or `inconclusive` — citing the confirmatory results it rests on and the evidence it was compared with. Negative results are recorded and reported.

## Data handling

- **Tool and data are separate.** This repository contains only the tool. Each project's data lives in that project's workspace.
- **Git-ignored by default.** `/rw-init` adds the following to the workspace `.gitignore`:
  - `data/` — datasets and anything that may identify a person
  - `literature/fulltext/` and `literature/inbox/` — copyrighted PDFs
  - `experiments/*/outputs/` — experiment outputs
  - `meetings/**/transcript.*` — meeting transcripts
- **Identifiable information** belongs in `data/` only and must not be copied into other artifacts. If it appears in meeting notes, the meeting workflow warns about it and leaves it out of the records it writes.
- `.gitignore` does not untrack files that were committed earlier. Check an existing project with `git ls-files data/` before pushing it anywhere.

## Safeguards

| Safeguard | How it works |
|---|---|
| Human-only gates | `/rw-approve` is hidden from the model. A pre-write hook also blocks the model from running the approval script by any route it can detect. |
| Frozen artifacts | The protocol after G1 and an experiment spec after G3 cannot be edited directly. Changes go through an amendment or a new experiment. Content digests are stored at approval, and `trace.py` reports any change made by other means. |
| Schema validation | Every artifact written is validated immediately; errors are returned to the model to fix. |
| No invented sources | Records come only from database responses or imported PDFs. DOIs are checked against Crossref, OpenAlex and DataCite. A failed search is logged and reported, never replaced from memory. |
| Independent verification | The verification agent has no write tools. It records verdicts through `audit.py` only. |
| Confirmed human input | Observations and comments from meetings are recorded only after the user confirms each one. A verbatim quote must appear in the notes or transcript. |
| Parallel safety | ID allocation and appends are serialized with a workspace lock, so parallel agents cannot collide. |

## Known limitations

- **Guardrails, not a security boundary.** The hooks stop the model from taking the human-only actions through ordinary paths, but they inspect command text and cannot catch every conceivable route. They are meant to prevent mistakes, not to withstand a determined adversary.
- **Confirmation depends on the workflow.** Scripts record `confirmed_by_user` when the skill says the user confirmed; they cannot independently prove it.
- **Not yet validated on a full project.** Behavior on real notebooks, real datasets and long projects is unproven. Expect rough edges.
- **PDF extraction limits.** Scanned PDFs yield no text, and complex tables may be extracted imperfectly.
- **Google Scholar is manual** by design (see above).
- **Known smaller gaps:** blank rows saved by spreadsheet software can fail validation; verbatim matching of Thai text copied from some apps can fail because of invisible characters (it falls back to paraphrase); Thai titles differing only in tone marks may be merged by de-duplication.
- **Not yet supported:** importing a project that already has results (retrospective mode), dataset content hashing and leakage checklists, multi-chapter reports, and hosts other than Claude Code. Adapters for Codex, Cursor and other tools are planned.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest
```

| Path | Contents |
|---|---|
| `skills/` | The eleven `rw-*` skills |
| `agents/` | The six specialist agents |
| `scripts/` | Deterministic tools and hooks |
| `schemas/` | JSON Schema, one per artifact type |
| `hooks/` | Hook configuration |
| `templates/` | Files copied into new workspaces |
| `tests/` | Test suite with a complete golden workspace fixture |
| `docs/spec/`, `docs/plan/` | Design specification and implementation plan |

## License and acknowledgements

Released under the [MIT License](LICENSE).

The design draws on ideas from the [PRISMA 2020](https://www.prisma-statement.org/prisma-2020-statement) reporting guideline, Anthropic's published description of its multi-agent research system, and the `academic-research-skills` project. No code or text was copied from these sources.
