---
name: claude-usage
description: Check the user's Claude plan usage — the 5-hour session limit and the 7-day weekly limit (percent used, time to reset). Use for "/claude-usage", "how much usage do I have left", "what's my session usage", "when does my limit reset", "am I close to the limit", and BEFORE launching anything expensive (workflows, fan-outs of many subagents) to decide whether there is headroom.
---

# Claude plan usage

Run the CLI; don't estimate usage from memory or from this conversation's length.

```bash
claude-usage          # human-readable
claude-usage --json   # structured, for decisions
```

`--json` shape:

```json
{
  "five_hour": { "used_percentage": 44, "resets_at": 1790341800, "resets_in_seconds": 6900 },
  "seven_day": { "used_percentage": 54, "resets_at": 1790499600, "resets_in_seconds": 164700 },
  "captured_at": 1790334860, "age_seconds": 12, "stale": false
}
```

A window is `null` when no live reading exists (e.g. the 5h window just rolled over and no session has made a call since).

## Exit codes

| code | meaning | what to do |
|---|---|---|
| 0 | fresh data | use it |
| 1 | no data (cache missing/unreadable) | say so; don't guess |
| 2 | stale (> 5 min old; override with `CLAUDE_USAGE_STALE_SECS`) | still printed; report it with its age |

## Reading it

- Limits are **account-wide**, shared by every running session and subagent — not per session.
- Report both windows with reset times, e.g. "5h: 44%, resets 15:10 · 7d: 54%, resets Sun 11:00". The human output already uses local time; report it in the user's timezone.
- Before an expensive run: if `five_hour.used_percentage` ≥ 80 or `seven_day.used_percentage` ≥ 90, tell the user the headroom and the reset time and ask before launching. Otherwise just mention the numbers.

## How it works (for troubleshooting)

- Your status-line command pipes its JSON input into `bin/claude-usage-capture`, which receives `rate_limits` from Claude Code on every status-line refresh and merges it into `~/.claude/usage-cache.json`: per window, the latest `resets_at` wins, then the higher `used_percentage`; expired or missing windows never overwrite good data. This is because many sessions write the file, and idle ones report stale/partial limits.
- `bin/claude-usage` only reads that file.
- It updates only while an **interactive** Claude Code session is open — headless `claude -p` runs don't run the status line. Stale data usually just means no interactive session is running.
