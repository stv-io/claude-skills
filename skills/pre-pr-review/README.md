# pre-pr-review

Before a change request goes to a shared repo, you review all of it locally in [crit](https://crit.md): the description the PR or MR will carry, and every file it changes, in one session.

You run `/pre-pr-review`, or ask for a pre-pr review in the prompt. Claude drafts the description (from the repo's PR template if there is one) and opens crit with the description first and each changed file as a diff. You comment, Claude revises the text or the code and replies in crit, and the loop repeats until you finish a round with no comments. Then Claude gives you the exact `gh`, `glab` or `bkt` command, using the approved text as the body. Nothing is opened until you say so.

Claude never starts it on its own (`disable-model-invocation: true`), so in repos where you don't want it, nothing changes.

- **Needs:** Python 3.9 or later, git, [crit](https://crit.md) (tested with 1.8.0).
- **Touches:** writes the draft to `.git/pre-pr-review/` in the repo (never committed, one per worktree). crit runs on 127.0.0.1.

```bash
bin/pre-pr-review info [BASE]       # branch, base, merge base, changed and deleted files, draft paths, PR template
bin/pre-pr-review init [BASE]       # create the draft folder; copy in the PR template if there's exactly one
bin/pre-pr-review crit-args [BASE]  # crit's arguments: the description, then every changed file
```

BASE defaults to origin/HEAD, then origin/main, origin/master, main, master. Changes are counted from the merge base to the working tree, so uncommitted edits and untracked files are included. Exit code 2 means git failed (a bad BASE, or not a repo).

## Limits

- Deleted files don't appear in crit, because there's nothing to open. The description names them instead.
- crit labels new files "modified" in its file list. The diff is still correct.
- Images in the description render in crit, but forges won't take local paths. Claude lists the attachments for you to drag into the PR once it exists.

## Running it automatically (not built)

v1 runs only when you invoke it. [docs/v2-plan.md](docs/v2-plan.md) holds the parked design for making it a default in shared repos: repo classes (on, off, ask), a size test so small changes skip it, and a hook on PR creation. [tools/classify/](tools/classify) builds a local page for sorting your repos into those classes.

## Tests

```bash
cd skills/pre-pr-review/tests
uv run --no-project --with pytest pytest -q
```
