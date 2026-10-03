---
name: rw-approve
description: Human-only approval of research gates G1–G4 and protocol amendments in a research-workbench workspace. Only the user can invoke it.
disable-model-invocation: true
argument-hint: "G1 | G2 [H-…] | G3 X-… | G4 | amend protocol/amendments/<file>.yaml  [--note \"reason\"]"
---

# Approve: $ARGUMENTS

Output of the approval script, which ran when the user invoked this command:

!`python3 "${CLAUDE_SKILL_DIR}/../../scripts/rw_state.py" approve $ARGUMENTS 2>&1; echo "exit=$?"`

Tell the user in Thai:
- `exit=0`: what was approved (gate, IDs, note) and the next step (`/rw-orchestrate`).
- non-zero exit: each problem the script listed, in plain words, and what fixes it.

Never run `rw_state.py approve` yourself; the guard hook blocks it. If the output above is missing (the command did not run), ask the user to run it themselves with:
`! python3 "<path to research-workbench>/scripts/rw_state.py" approve $ARGUMENTS`
