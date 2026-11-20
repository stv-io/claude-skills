# v2 plan: running pre-pr-review automatically

**Status:** parked. v1 runs only when invoked. This is the design for making it a default in
shared repos without touching personal ones, kept so v2 doesn't start from scratch.

## Two tests decide

A change gets a review only if both tests say so.

**1. The repo's class.** The first source that answers wins:

| # | Source | Example |
|---|--------|---------|
| 1 | Local git config, for one repo, never committed | `git config --local pre-pr-review.class off` |
| 2 | `~/.config/pre-pr-review/rules`, where the most specific match wins | `bitbucket.org/<team>/*  on` |
| 3 | Default for a repo nobody classified | **on**, and Claude asks once at its first PR, then records the answer |

| Class | Meaning |
|-------|---------|
| on | Review every change that isn't small |
| off | Never review |
| ask | Claude asks at PR time with a recommendation, e.g. public personal repos |

**2. The change's size.** A change is small if all of these hold:

- 30 or fewer changed lines, not counting lock files and generated files;
- 3 or fewer files;
- no added, deleted or renamed files;
- nothing from an "always big" list: CI config, IAM and policy files, Terraform resource
  changes.

Small changes skip the review in every class. The thresholds are overridable in the rules file,
and a decision log lets them be tuned later.

**Re-review after approval:** only when the change since the approved commit isn't small.

## Triggers

- One line in the global `CLAUDE.md`: `docs-sweep` → `pre-pr-review` → open the PR.
- A `PreToolUse` hook on Bash, matching `gh pr create|glab mr create|bkt pr create`. It blocks
  until the review has passed or been skipped for HEAD, and passes personal repos and small
  changes through untouched.

```bash
#!/usr/bin/env bash
cmd=$(jq -r '.tool_input.command // ""')
echo "$cmd" | grep -Eq '(gh pr create|glab mr create|bkt pr create)' || exit 0
verdict=$(pre-pr-review gate 2>&1) && exit 0     # gate = class + size + approved/skipped record for HEAD
echo "pre-pr-review: $verdict" >&2
exit 2
```

## Seeding the rules file

`tools/classify/` builds a local page that lists every repo under a folder, grouped by forge
owner, with bulk on/off/ask buttons and a rules file to copy out:

```bash
python3 tools/classify/inventory.py ~/code > /tmp/repos.json
python3 tools/classify/build_classifier.py /tmp/repos.json /tmp/classify-repos.html
open /tmp/classify-repos.html
```

The page and the inventory list your repo names, so keep them out of this repo. A cheaper start
than classifying hundreds of repos: set only the owners where PRs actually go, and let the
ask-once default pick up the rest.

## Options rejected

- A committed opt-in marker in each repo: it clutters shared repos.
- Gating on the folder alone: worktrees and odd clone locations are misjudged.
- Gating on the number of contributors: a new work repo with one committer looks personal.
- Default off: another thing to remember for every new client repo.
- `crit --pr` on a draft PR: by then others can already see the change.
