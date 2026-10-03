---
name: rw-progress
description: Build a progress-review document for an advisor meeting from the research-workbench artifacts (work done since the last review, results, comment status, hypotheses, open issues). Use before meeting the advisor or when the user asks for a progress summary.
argument-hint: "[YYYY-MM-DD]"
---

# rw-progress

`$S` = `${CLAUDE_SKILL_DIR}/../../scripts`

1. Date: from `$ARGUMENTS`, else today. Run `sh "$S/rw" progress.py --date <date>`.
   If the file already exists, ask before rebuilding it with `--force`.
2. Read `progress/<date>-review.md`. The script wrote all tables and numbers from artifacts; you may only:
   - add a summary of at most 5 lines under the header, in Thai, that cites IDs
   - add 3–6 questions or decisions for the advisor under the HTML comment in section 5, each tied to a K/H/X/R ID
   Never change numbers, tables or statuses.
3. Show the user the summary and questions, and edit them together.
4. Offer to create the meeting now: `sh "$S/rw" meeting.py new --type advisor-review --date <date> --role advisor`.
   After the meeting, run `/rw-meeting log M-…` to record comments.
