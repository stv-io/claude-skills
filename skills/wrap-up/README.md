# wrap-up

**Before you `/exit`, `/wrap-up` makes sure nothing you care about is left loose. It finds uncommitted and unpushed work, runs the repo's checks, asks what to do with each change, lists loose ends and next steps, and ends with a summary in the chat.**

`/exit` just exits. Uncommitted edits, a dev server still running, an unpushed branch, a lesson you meant to note — none of that stops it. `/wrap-up` goes through them with you:

1. **Inventory:** uncommitted and unpushed work, other worktrees, background work, TODOs added this session.
2. **Checks:** the repo's tests and lint, before any commit is offered.
3. **Each change, your choice:** commit, WIP commit, leave as is, or discard. Discard only after you type `discard`.
4. **Offers, never automatic:** a push, lessons for `CLAUDE.md` or memory, next steps for your task list, a `/rename` name.
5. **Summary block** with a verdict: ✅ safe to exit, ⚠️ safe but something stays loose, or ⛔ not yet.

It writes no handoff file. The summary stays in the conversation, and after `claude --resume`, [`/whats-up`](../whats-up) starts from it.

## Safety

- It never pushes, opens a PR, force-pushes or skips hooks unless you ask for that exact step.
- No bare `git stash`, because the stash list is shared with every worktree and session. Work set aside becomes a `WIP:` commit.
- Nothing is discarded until it has listed exactly what would be lost and you've typed `discard`.
- It sends no messages. Anything that should be sent is drafted for you.
- Wrap-up or pre-PR steps in your `CLAUDE.md` or `AGENTS.md` are followed too.

## Install

```bash
npx skills add stv-io/claude-skills --skill wrap-up -g
```

## What you need

- **git.** Optional: **`gh`**, to see the PR.

## What it looks like

```markdown
## Wrap-up — webhook retry backoff · 2026-11-18 16:40 UTC

**Verdict:** ⚠️ Safe to /exit, but 2 commits are unpushed (you chose not to push)

**Shipped:** 4e1a9c2 backoff with jitter · 7b20d1e README: retry settings
**Stuck / dropped:** queue-based retry (needs Redis)
**Left as is:** 2 unpushed commits on feat/retry-backoff
**Decided:** 30 s cap, not configurable
**Open:** should 408 retry too?

**Next session, start here**
1. Push and open a PR: `git push -u origin feat/retry-backoff`
2. Ask the API owner about 408

Resume: `claude --resume 3f6c2a1e` · suggested `/rename webhook retry backoff`
```

## Triggers

`/wrap-up`, "wrap up", "let's finish here", "close out the session", "is it safe to exit", "end of day".
