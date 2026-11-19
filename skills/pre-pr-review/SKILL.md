---
name: pre-pr-review
description: Review a change request locally in crit before it becomes a PR or MR. Claude drafts the description (following the repo's PR template), opens it in one crit session together with every changed file as a diff, revises both until the user approves, then hands over the exact PR or MR command, using the approved text as the body. Runs only when the user invokes it with "/pre-pr-review" or asks for a "pre-pr review" in the prompt.
disable-model-invocation: true
---

# pre-pr-review

You review the whole change request before anyone else sees it: what the PR or MR will say, and
what it changes. Both are in one crit session. You comment, Claude revises, and the loop repeats
until you approve. Then the PR is opened with exactly the text you approved.

**Run it only when asked.** The user invokes it. Never start it yourself, even right before a PR.
It doesn't replace the user's go-ahead for opening the PR.

```bash
pre-pr-review info [BASE]       # JSON: branch, base, merge base, changed and deleted files, draft paths, PR template
pre-pr-review init [BASE]       # create the draft folder; copy in the repo's PR template if there is exactly one
pre-pr-review crit-args [BASE]  # crit's arguments, one per line: the description, then every changed file
```

It is `bin/pre-pr-review` in this skill's folder (Python 3.9+, standard library). BASE defaults to
origin/HEAD, then origin/main, origin/master, main, master. If the user passed a base
(`/pre-pr-review develop`), use it. Exit 2 means git failed, usually because the BASE doesn't
exist. Fix the BASE; don't carry on.

## Steps

1. **Read the state.** Run `pre-pr-review info`. Check it with the user in one line: branch, base,
   number of commits and files. If `uncommitted` is true, say so. The review shows the working
   tree, so uncommitted edits are included, but the PR will contain only what gets committed and
   pushed. Ask whether to commit first or to review as it is.
2. **Sweep the docs** if the repo is one `docs-sweep` covers (infrastructure code with a README or
   `docs/`), and fix what it finds before drafting. The review should show the finished branch.
3. **Draft the description.** Run `pre-pr-review init`, then write `description` (the path `info`
   gives, under the git dir, so it's never committed):
   - The first line is `# <PR title>`, followed by the body. At hand-off the title is taken from
     this line.
   - If the repo has a template, fill it in. If there are several, choose the one that fits and
     say which one you used. Read the repo's `CONTRIBUTING`, `AGENTS.md` and `CLAUDE.md` for PR
     rules, plus any naming rules from the user's skills (e.g. a Jira key in the title).
   - Write it for the reviewers: what changed and why, how it was tested, the risk and the
     rollout, and anything the reviewer must look at. List deleted files by name, because the
     diff view can't show them (see below).
   - Put screenshots and diagrams in `assets_dir` and link them with relative paths
     (`![plan](assets/plan.png)`).
4. **Open crit.** Run crit from the repo root **in the background**, with the arguments from
   `crit-args`:

   ```bash
   cd "$(git rev-parse --show-toplevel)" && pre-pr-review crit-args | tr '\n' '\0' | xargs -0 crit
   ```

   Pass the user the URL crit prints: *"crit is open at http://localhost:NNNN: the description is
   the first file, then the diff. Comment, then click Finish Review."* Wait for crit to exit. Don't
   read the review early.
5. **Revise.** When crit exits, read what it printed. For each comment, edit the description or
   the code, then reply in crit (`crit comment --reply-to <id> --author 'Claude Code' '<what you
   did>'`; use `--json` for several replies). Don't resolve comments yourself. If a code change
   adds or removes a file, run `crit-args` again. Then start the next round with the same command
   and wait again. Stop when a round finishes with no comments.
6. **Hand over.** Show the final title, the source and target branch, and the exact command,
   with the approved body passed as a file:

   | Forge | Command |
   |-------|---------|
   | GitHub | `gh pr create --base <base> --title "<title>" --body-file <body>` |
   | GitLab | `glab mr create --target-branch <base> --title "<title>" --description "$(cat <body>)"` |
   | Bitbucket | `bkt pr create`, with the title and the body from `<body>` (check `bkt pr create --help` for the flags) |

   `<body>` is the description without its `# title` line. Write it next to the description as
   `body.md`. Opening the PR needs the user's go-ahead, as always. Approving the review is not
   that go-ahead. If the user says to open it, push first if the branch isn't on the remote.
   - **Attachments:** forges don't accept local relative image paths. List each file in
     `assets_dir` for the user to drag into the PR or MR once it exists, and say where each one
     goes. Don't upload them anywhere yourself.

## What crit shows, and what it doesn't

Tested with crit 1.8.0:

- **One session, two parts:** passing the description and the changed files as file arguments
  gives one crit session. The description is rendered as markdown and each code file as a diff
  against the base branch.
- **Uncommitted edits are included.** crit diffs the working tree, and its scope picker switches
  between all changes, the branch's changes and the unstaged ones. Don't use `crit --range`
  here: it ignores file arguments, so the description wouldn't show, and it leaves out
  uncommitted edits.
- **Deleted files are not shown,** because crit can't open a file that's gone. `info` lists them
  under `deleted`, and the description must name them.
- **New files are labelled "modified"** in crit's file list. That's cosmetic, and the diff is
  still correct.
- **Images in the description:** crit's image handling is for comment attachments. A relative
  image link in the description probably won't render. Check by eye the first time, and if it
  doesn't render, point the user at the file in `assets_dir`.

## Afterwards

The draft folder stays in the git dir so a second review can start from the approved text. When
the PR is merged or abandoned, offer to delete it (`rm -r` on `draft_dir`, after the user says
yes).
