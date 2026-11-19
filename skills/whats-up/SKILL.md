---
name: whats-up
description: Catch the user up on the current Claude Code session when they have lost the thread — what it is about, where it stands, what comes next, and what Claude needs from them — checked against git and live state, not from memory. Use for "/whats-up", "what's up", "catch me up", "where are we", "what were we doing", "remind me what this is", "what's the status", "what do you need from me", or when the user comes back to a session after a break and seems lost. Read-only: it starts no work.
---

# whats-up

The user has come back to this session and lost the thread. Answer four questions in about 10–15 lines, then stop. Claude Code's own `/recap` already gives a one-line recap (400 characters at most). This skill goes further, with the status checked against the repo, the next step, and the decisions waiting on the user.

**Do no work.** Make no edits, commits or tool calls that change anything. Read, check, report and offer.

## 1. Gather

Run these before writing. The status comes from checks, not from what you remember.

- **The conversation.** Find the user's goal and how it changed, what was done, what failed or was dropped, decisions made, and questions you asked that were never answered.
  - If the context was compacted, the summary may have lost the early prompts. If `session-export` is installed, `session-export --prompts` lists every prompt in this session.
  - If the conversation holds a `/wrap-up` summary block, start from the latest one and check it below. Don't copy it.
- **Git**, in each repo this session worked in:
  - `git status --short`, the branch, and `git log --oneline @{u}..` for unpushed commits (or the commits since the base branch if there's no upstream).
  - `git worktree list` if the session used worktrees.
  - If `gh` is available, check for an open PR on the branch: `gh pr view --json number,state,url,statusCheckRollup`.
- **Live state.** Background tasks or subagents still running, and dev servers or watchers this session started. If the session keeps a tracker or status file (for example a `status.json` from tracker-page, a todo list or a `PROGRESS.md`), read it.

## 2. Check the record against reality

Where the conversation or a wrap-up block says one thing and git or live state says another, report what is true now and name the gap. Examples: "you were told this was committed, but `foo.py` is modified", or "the wrap-up said 3 unpushed commits; there are now 4". If something can't be checked, call it **unknown**. Never guess it as done.

## 3. Answer

Use this exact shape. Put **Need from you** first whenever it has anything in it, because it is the reason the user is stuck.

```markdown
**Need from you**
1. <a decision, approval, login or input, written so a one-word answer works: "Push the branch and open a PR? (yes/no)">

**About** — <the goal in one line>. <If it drifted: "Started as X, now Y.">

**Status**
- Done: <item> (<evidence: commit abc1234 / PR #12 / tests passed at 14:02>)
- In progress: <item and how far it got>
- Stuck or dropped: <item and why, so the user doesn't suggest it again>
- Repo: <branch> · <N> uncommitted files · <N> unpushed commits · <PR state> · <background work>

**Next** — <the single next action>. Then: <the one or two after it>.
```

- If there's nothing to ask, write "**Need from you** — nothing" and put it last.
- Separate what was **decided** from what is still **open**. Don't present an open question as settled.
- Give file and commit references (`path:line`, short SHA) so the user can check the evidence.
- No history lesson. Leave out finished side quests unless they changed the plan.
- Write every time in the user's preferred time format and timezone.

## 4. Stop

End with one line that offers the next action ("Want me to carry on with <next>?") and wait. If the session looks finished, suggest `/wrap-up`.
