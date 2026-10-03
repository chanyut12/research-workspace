---
name: rw-init
description: Create a research-workbench workspace (state, folders, CLAUDE.md rules, .gitignore) in a new or existing project folder. Use when the user starts a research project or wants to put an existing project under research-workbench.
argument-hint: "[directory] --title \"<project title>\""
---

# rw-init

Scripts live in `${CLAUDE_SKILL_DIR}/../../scripts` (call it `$S` below; always quote paths).

1. Run `python3 "$S/check_deps.py"`. If it reports missing packages, show the user the install command it prints and wait until they confirm.
2. Directory: the one given in `$ARGUMENTS`, else the current directory. Title: from `$ARGUMENTS`, else ask the user.
   If the directory already has files, tell the user that an existing CLAUDE.md and .gitignore get appended to, never overwritten, and get a yes.
3. Run `python3 "$S/init_workspace.py" "<dir>" --title "<title>"`.
4. Run `python3 "$S/validate.py" --workspace "<dir>"`. It must print OK.
5. Tell the user, in Thai:
   - patient data goes only in `data/` (git-ignored); PDFs go in `literature/fulltext/` (git-ignored)
   - next step: `/rw-protocol` to draft the research question, or `/rw-orchestrate` to be guided
   - meetings with the clinician or advisor can be recorded any time with `/rw-meeting`
