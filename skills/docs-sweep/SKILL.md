---
name: docs-sweep
description: Before a change becomes a PR or MR, sweep the whole repo's docs for everything the change makes stale, not only the lines the diff touches. Use in any repo that holds infrastructure code and docs (Terraform, Terragrunt, OpenTofu, Helm, Helmfile, Kubernetes manifests, CI config, scripts, with a README or a docs/ tree). Use for "/docs-sweep", "sweep the docs", "are the docs still right", "check the docs for this PR / MR", "update the docs for this change", and, without being asked, as the last step before a branch in such a repo goes to review or becomes a PR or MR.
---

# docs-sweep

A change is not done until every page that describes what it changed is true again. The diff
shows the docs the author remembered. This skill finds the ones they did not: the README status
line, the layout tree, the count in a sentence ("six jobs"), the version in a table, the "not
built yet" that is now built, the comment in another file that says "keep in step with".

The script finds candidates. You judge them. A hit is a place to look, not proof of an error.

```bash
docs-sweep all [BASE]     # the four checks below; BASE defaults to the remote's default branch
docs-sweep terms [BASE]   # values the change removed or replaced that the repo still mentions
docs-sweep paths          # a/b file paths named in Markdown that are not in the repo
docs-sweep links          # relative Markdown links and #anchors that do not resolve
docs-sweep claims         # counts and versions in Markdown that disagree with the repo
```

It is `bin/docs-sweep` in this skill's folder (Python 3.9+, standard library, read-only). Run it
from inside the repo, on the branch under review. `terms` compares the merge base with the working
tree, so uncommitted edits count; new files that are not git-ignored are checked as well. If it
exits 2, git failed (usually a BASE that does not exist): fix the BASE, do not read it as clean.

## Steps

1. **Read the repo's own rules first.** `AGENTS.md`, `CLAUDE.md`, the contributing section, the
   docs index. They say where each kind of fact belongs and what an MR must update. Follow them
   over this page where they differ.
2. **List what the change changes, as facts.** Read `git diff BASE...HEAD` and write the list for
   yourself, old value and new value where there is one:
   - names: resources, units, releases, charts, files, scripts, flags, variables, users, roles;
   - numbers: versions, sizes, counts, ports, timeouts, limits, CIDRs, instance types;
   - behaviour: order of steps, defaults, what is on or off, what a command now does or needs;
   - existence: something added, removed, renamed, moved, replaced;
   - status: something planned that is now built, or built that is now gone.
3. **Run `docs-sweep all`.** Then search by hand for what a script cannot see: for each fact in
   the list, grep the old value, the name, and the words a person would use for it, across the
   whole repo. Docs are not only `*.md`: also comments in code and values files, chart and module
   READMEs, MR and issue templates, skills and agent instructions, diagram sources, example
   commands, test descriptions, dashboards' text.
4. **Check the places that go stale silently**, whether or not the search hit them:
   - the README: status, feature list, quick start, layout tree, troubleshooting;
   - index pages: every page listed exists, every page that exists is listed;
   - tables of "what is built" and "where it lives"; lists of "later", "planned", "not yet",
     "open points", "TODO": does the change make an entry true, false, or done?
   - counts and enumerations in prose ("the three users", "five tests", "both clusters");
   - commands shown in docs: the script, flag and path still exist and still do that;
   - versions written in prose against the pins in code;
   - the same fact stated in two places: after the change, do they still agree?
   - diagrams: if the picture is now wrong, change its source and re-render, or say it is stale;
   - setup and teardown steps, when the change creates anything outside state or adds a tool;
   - tests' own descriptions of what they check.
5. **Decide for each candidate.** One of:
   - **Stale:** fix it in this branch.
   - **Still true:** leave it.
   - **History:** a decision record, changelog, lessons log, dated note or migration write-up
     describes what was true then. Do not rewrite it. If the change supersedes it, add a
     dated pointer to what replaced it, in the form the repo uses.
   - **Wrong before this change, unrelated to it:** do not fix it here. Report it as a follow-up.
6. **Fix with the smallest edit that makes the page true.** Match the page's style. Do not reflow
   paragraphs or tables you did not need to touch, and do not improve prose on the way past: other
   branches edit the same pages. Never write a claim you have not checked against the code, and
   never state live state (what is deployed, what passes) unless you checked it in this session.
7. **Run `docs-sweep links` and `paths` again** after editing, plus the repo's own checks
   (pre-commit, linters, the docs build if there is one).
8. **Report**, short:
   - fixed: file, line, what was stale, what it says now;
   - left alone on purpose, with the reason (history, still true);
   - follow-ups: stale docs the change did not cause;
   - not checked: anything you could not verify (live state, a diagram you could not render).
   If nothing needed changing, say so and say what you searched for.

## Judgement

- **Scope is "affected by this change", widely read.** A page is in scope when a reader who
  trusted it after the merge would be misled because of this change. It is not a licence to
  rewrite the docs.
- **Old values matter more than new ones.** The new name is where the author already looked. The
  old name is what is still lying around.
- **A doc-only change needs the sweep too:** it can contradict another page.
- **When the docs and the code disagree and you cannot tell which is right,** do not pick. Report
  both, with file and line.
- **Do not weaken a warning to make the docs agree** ("dev only", "never do X in production").
  If the change removes the reason for it, say that in the report and let a person decide.
- **Big repos:** hand the search to a cheaper sub-agent. Give it the fact list from step 2, the
  script's output and the rules in steps 5 and 6, ask for candidates with file and line, and judge
  the candidates yourself. Review any edit it makes as you would a colleague's.

## What the script does and does not do

| Check | Finds | Misses |
|---|---|---|
| `terms` | Names and values on removed lines of the diff that no added line contains, and deleted or renamed paths, wherever the repo still mentions them | Facts the diff does not spell out (behaviour, order, counts), synonyms, values that changed meaning but not text |
| `paths` | Backticked `a/b` file paths in Markdown that do not exist in the repo | Bare file names (`LOG.md` is as often an example; a deleted or renamed file's name is a `terms` hit); paths outside backticks; paths in another repo (reported, judge them); generated files |
| `links` | Relative links to missing files and `#anchors` with no matching heading (GitHub and GitLab anchor forms) | External URLs; anchors made by a site generator |
| `claims` | "N &lt;folder name&gt;" where the folder holds a different number of sub-folders (`seven skills` when `skills/` has 8); a pinned name followed by a version that disagrees with the pin (`Terraform 1.9` against `required_version = "1.12.6"`). Pins come from Terraform/Terragrunt version constraints, module `source` + `version`, Helm `chart`/`name` + `version`/`targetRevision`, image tags, `uses: x@v4`, `.tool-versions` and `.terraform-version`. A module's README is compared with its own folder's pins when it has any. Changelogs are skipped | Counts of things that are not folders ("five tests"); subsets (`two skills need setup` is reported; judge it); versions of things nothing pins; versions further than a few words from the name |

Exit code is 1 when anything is reported and 2 when git fails. Exit 1 is meant for a person or a model to read, not as a
hard gate: history pages legitimately name files that are gone.
