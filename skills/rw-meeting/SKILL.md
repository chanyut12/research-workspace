---
name: rw-meeting
description: Prepare for and record meetings in a research-workbench workspace (clinician/expert consultations, advisor progress reviews, self notes), turning notes or transcripts into user-confirmed observations (O-xxx) and comments (K-xxx). Use when the user is about to meet or has just met their doctor/expert or advisor, or pastes meeting notes.
argument-hint: "new | prep M-nnn | log M-nnn"
---

# rw-meeting

`$S` = `${CLAUDE_SKILL_DIR}/../../scripts`

## new
Ask for the type (expert-consult, advisor-review or self-note), the date, and the participant roles (e.g. clinician, advisor; names optional). Then run:
`python3 "$S/meeting.py" new --type <type> --date <YYYY-MM-DD> --role <role> [--role …] [--agenda "…"]`
Tell the user where `notes.md` is. If they have a transcript, run `python3 "$S/meeting.py" attach-transcript M-… <file>`.

## prep M-nnn
1. Read `python3 "$S/rw_state.py" status`, `python3 "$S/trace.py"`, `python3 "$S/comments.py" summary`, the hypotheses and the latest results.
2. Draft 5–10 questions using `references/prep-questions.md` for the meeting type. Each question names the H/X/R/K it is about.
3. Edit the questions with the user, then run `python3 "$S/meeting.py" prep M-… --question "…" [--question "…"]`.
4. For an advisor review, also run `/rw-progress`.

## log M-nnn
1. Read the meeting's `notes.md` (the main input: short bullets, Thai/English mixed), and the transcript if one is attached. Read long transcripts in chunks of about 300 lines.
2. If the text has patient-identifying details (names, HN, ID numbers, exact birth dates, addresses), warn the user and leave them out of everything you record.
3. Show the candidates as one table: # | kind (O or K) | speaker role | text | form/basis or severity/target | source_ref (line or timestamp).
   - O = observation, opinion or hypothesis idea from a person. `verbatim` only if the exact words appear in the notes or transcript; otherwise `paraphrase`.
   - K = something the advisor or expert wants done or changed; target is an H/X/R/C ID or `general`; severity must/should/consider.
   - If it is unclear who said something or what it means, ask. Do not guess.
4. The user confirms, edits or drops each row. Write nothing before that.
5. For each confirmed row:
   - `python3 "$S/meeting.py" add-observation M-… --role … --statement "…" --form … --basis … --ref …`
   - `python3 "$S/meeting.py" add-comment M-… --target … --text "…" --severity … --ref …`
6. For each new O that could be tested on the data, offer a draft hypothesis (origin expert or advisor). If the user agrees, dispatch synthesis-agent to add it as proposed, then run a literature check with `/rw-search H-… both`.
7. Run `python3 "$S/meeting.py" logged M-…` and `python3 "$S/trace.py"`. Report the new O/K/H IDs.
