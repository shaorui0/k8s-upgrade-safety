---
name: upgrade-change-loop
description: The fixed loop for every change in this repository: OpenSpec change -> implement -> acceptance -> HTML report + blog notes -> staged commits. Use when the user says "do the next change", "follow the loop", "commit this change", or when starting any code or doc change here.
---

# upgrade-change-loop

One change = one OpenSpec change = **several commits, one per stage** (never one big commit). A change without acceptance evidence is not done.

## Steps

1. **Open the change**: `openspec new change c<NNNN>-<slug>` (OpenSpec needs a leading letter, hence the `c`; four digits, next number after the largest in `reports/`). Write proposal and tasks; tasks must contain an acceptance item that names the command or test that proves it is done.
2. **Implement**: change only what the tasks list.
3. **Acceptance**: run the acceptance commands and store the output **verbatim** in `openspec/changes/<id>/evidence.md`. If it fails, go back to 2; do not move on.
4. **HTML report**: `reports/<NNNN-slug>.html`. What changed, why, acceptance evidence, before/after. A local HTML file, never a published artifact. Write markdown first, then `pandoc -s --metadata title=<slug> in.md -o reports/<NNNN-slug>.html`.
5. **Blog notes**: `notes/blog/<NNNN-slug>.md`. Only the core ideas, the pits, the counter-intuitive conclusions, as bullets. **No writing polish.**
6. **Commit per stage**: when a stage is done, commit it, `git add` only that stage's files (never `-A`). First line: `c<NNNN>-<slug> [k/n <stage>]: <one sentence>`:
   - `proposal`: proposal.md (why)
   - `spec+tasks`: specs/, tasks.md (what done looks like, how it is verified)
   - `impl`: code or config (may be several impl commits, each passing the unit tests on its own)
   - `docs`: documentation, README, skill
   - `acceptance`: evidence.md + HTML report + blog note + **one row appended to the README `## Progress` table** (Change / Date / What / Takeaway = first line of the blog note / links to report and note); the body lists the acceptance verdict
   Skip stages that do not exist; n is the actual number of stages.
7. **Report the acceptance** to the user in the main agent: pass or fail, key output, path of the HTML report. Not reported = not done.
8. When finished, `openspec archive <id>` (may be batched with the next change).

## Hard rules

- Every markdown the user is meant to read also exists as HTML.
- Nothing from any employer enters the repository: no names, no cluster aliases, no internal services, no account numbers. Clean-room: only the two public write-ups are source material. Run `python3 tools/check_rules.py` before every acceptance commit and `git diff --cached` before every commit.
- Every number in a report points back to evidence or a data row.
- Anything that would act on real infrastructure needs a human gate and a rollback written in the proposal. (The simulator never touches real infrastructure; the rule is for whoever ports it.)
- Commit messages end with the co-author trailer the session was given.
