---
name: wrap-up
description: Bring the current Claude Code session to a clean stop so the user can /exit safely — inventory uncommitted and unpushed work, run the repo's checks, settle each loose change with the user (commit, WIP commit, leave, or discard with typed confirmation), list loose ends, propose next steps, and end with a summary block in the chat. Use for "/wrap-up", "wrap up", "wrap this up", "let's finish here", "close out the session", "get me to a point where I can exit", "is it safe to exit", "end of day".
---

# wrap-up

Get the session to a point where `/exit` loses nothing the user cares about, and leave a summary in the chat that a later `/whats-up` (after `claude --resume`) can start from. **Write no handoff file.** The summary block at the end is the only record.

Run this in the main conversation, never in a subagent: a subagent doesn't have the session's context, and that context is the whole point.

## Safety rules (these override everything below)

- **Never discard work without a typed confirmation.** Before any `git restore`, `git checkout -- …`, `git clean`, `git reset --hard`, branch delete or file delete, list exactly what will be lost (files and line counts). Then wait for the user to type the word `discard`. "Yeah, get rid of it" is not enough.
- **No bare `git stash`.** The stash list is shared with other worktrees and other sessions. To set work aside, make a WIP commit: `git commit -m "WIP: <what>"`.
- **No push, no PR, no `--force`, no `--no-verify`** unless the user asks for that exact step in this wrap-up. "Wrap up" alone does not grant it.
- **Sending messages is out of scope.** If a message is needed (a PR comment, a Slack note to the team), draft it in the summary for the user to send.
- **The repo's own rules win.** If `CLAUDE.md` or `AGENTS.md` (repo or user level) sets wrap-up, pre-PR or commit rules, follow them as well. Examples: a docs sweep, a changelog entry, a commit-message format.

## 1. Inventory (read only)

For each repo this session worked in:

```bash
git status --short --branch
git diff --stat                       # unstaged changes
git diff --cached --stat              # staged changes
git log --oneline @{u}.. 2>/dev/null  # unpushed (no upstream: compare with the base branch)
git worktree list                     # other worktrees with changes?
```

Also check:
- **Background work:** background tasks, subagents, or dev servers and watchers this session started.
- **TODOs added this session:** `git diff -U0 <session start or base> | grep -nE '^\+.*\b(TODO|FIXME|XXX)\b'`.
- **Scratch files** this session created inside the repo that aren't meant to stay.

## 2. Checks

Run the repo's own fast checks on the working tree: tests, lint and type check, whichever the repo has (look at `CLAUDE.md`, the README, `Makefile`, `package.json`, `pyproject.toml` or CI config). Report failures before offering any commit. A commit that knowingly includes a failure has to say so in its message, and only if the user chooses that. Never call a failure "flaky" without evidence.

If the repo has no checks, or they take more than a few minutes, say so and skip them.

## 3. Settle each loose change

Group the uncommitted changes into logical units, such as one feature or one doc fix. For each unit, show the files and a one-line description, then ask which of these the user wants:

1. **Commit.** You propose a message in the repo's style (read `git log --oneline -10`).
2. **WIP commit.** Unfinished work, kept safe with a message starting `WIP:`.
3. **Leave as is.** It stays uncommitted. The summary says so.
4. **Discard.** Only after the confirmation in the safety rules.

Use one multiple-choice question for all units where the tool allows it, rather than one round per file. Then deal with:
- **Unpushed commits:** say they exist and offer to push. Push only after a yes.
- **Background work:** for each item, offer to stop it or leave it running. Say what leaving it means (for example, "the dev server on :3000 keeps running after you exit").
- **Other worktrees** with changes: report them. Don't touch them.

## 4. Lessons and next steps (offer, don't write)

- **Lessons:** if the session taught something lasting (a gotcha, a project convention, a preference the user stated), propose it as a short diff to the right memory file or `CLAUDE.md`. Apply it only on a yes. Lasting facts belong there, not in the summary.
- **Next steps:** list them in order. If a task or todo skill is installed, offer to file them there, one yes per item. Never file them unasked.
- **Session name:** suggest a 3–6 word name for `/rename`. Only the user can run it.

## 5. Summary block

Finish with this block and nothing after it. Keep it short, because a later `/whats-up` or the user scrolling back reads it.

```markdown
## Wrap-up — <goal in a few words> · <date and time>

**Verdict:** ✅ Safe to /exit | ⚠️ Safe to /exit, but <what stays loose> | ⛔ Not yet: <why>

**Shipped:** <commits with short SHAs, PRs, files made>, or "nothing committed"
**Stuck / dropped:** <what failed and why>, or "none"
**Left as is:** <uncommitted files, unpushed commits, processes still running>, or "nothing"
**Decided:** <decisions this session made>
**Open:** <questions still open>

**Next session, start here**
1. <first action, with the file or command>
2. <…>

Resume: `claude --resume <session id or name>` · suggested `/rename <name>`
```

- ✅ only when the working tree is clean (or every leftover is one the user chose to leave), checks passed or were skipped on purpose, and nothing runs that the user didn't choose to keep.
- Use the timezone and time format the user prefers.
- The session id is the folder above your scratchpad (`…/<session-id>/scratchpad`), or the newest `*.jsonl` in `~/.claude/projects/<cwd with non-alphanumerics as '-'>/`. If you can't tell, write `claude --resume` (it shows a picker).
