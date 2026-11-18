# whats-up

**You come back to a long session and can't remember what it was doing. `/whats-up` answers four questions: what this session is about, where it stands, what's next, and what Claude needs from you. The status comes from git and live state, not from memory.**

Claude Code's built-in `/recap` gives a one-line recap (400 characters at most). `/whats-up` is the longer version, for when one line isn't enough:

- **Need from you** comes first whenever there's anything in it. Each item is written so a one-word answer works.
- **Status** separates done (with a commit, PR or test run as evidence), in progress, and stuck or dropped. That way you don't suggest something that has already failed.
- It checks what the conversation says against `git status`, unpushed commits, the open PR and background work, and points out where they disagree.
- It's read-only. It starts no work and ends by offering the next step.

If the session has a [`/wrap-up`](../wrap-up) summary in it, `/whats-up` starts from the latest one and checks it against the repo.

## Install

```bash
npx skills add stv-io/claude-skills --skill whats-up -g
```

## What you need

- **git.** It works without git too, but then the status rests on the conversation alone.
- Optional: **`gh`**, to show the PR and its checks, and [session-export](../session-export), to recover the early prompts after the context was compacted.

## What it looks like

```markdown
**Need from you**
1. Push `feat/retry-backoff` and open a PR? (yes/no)
2. Keep the 30 s cap or make it configurable? (keep/config)

**About** — Add exponential backoff to the webhook sender. Started as a bug fix for duplicate deliveries.

**Status**
- Done: backoff with jitter (commit 4e1a9c2), tests for 429 and 503 (passed 14:02)
- In progress: README section on retry settings, half written
- Dropped: a queue-based retry. Needs Redis, which this service doesn't have
- Repo: feat/retry-backoff · 1 uncommitted file · 2 unpushed commits · no PR · nothing running

**Next** — finish the README section. Then: push, PR.

Want me to carry on with the README section?
```

## Triggers

`/whats-up`, "what's up", "catch me up", "where are we", "what were we doing", "what's the status", "what do you need from me".
