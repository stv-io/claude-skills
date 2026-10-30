---
name: session-export
description: Export a Claude Code session as clean, shareable Markdown — numbered prompts, Claude's original answers, tool calls collapsed, a contents list and outcomes, home paths and credentials masked. Use for "/session-export", "export this session/thread/conversation", "share this session with the team", "write up this conversation as markdown", or when /export output is broken (box-drawing tables, wrapped diffs).
---

# Session export

Run the CLI; don't hand-write a transcript from memory. It is `bin/session-export` in this skill's folder; if `session-export` isn't on your PATH, run it by that full path.

```bash
session-export --prompts                          # this session's numbered prompts
session-export -o ~/out.md                        # whole session (latest in the current directory)
session-export --from 3 --to 9 -o ~/out.md        # a range
session-export --stop-at '^Can you export' -o ~/out.md
session-export --list                             # other sessions here; pass an ID prefix to export one
```

Other flags: `--title`, `--start-at REGEX`, `-C DIR` (another project), `--no-outcomes`.

## Doing it

1. Run `--prompts` and pick the range. Usually leave out the export request itself and anything off-topic (side questions, the export clean-up). If the scope isn't obvious, ask.
2. Default title is the session's auto-title. Pass `--title` with a descriptive name when it's going to a team.
3. Write to the path the user gave, or `~/<slug>.md`.
4. Read stderr. If it reports masked values, tell the user how many and of what kind, and that they should check the `«redacted»` spots.
5. Before calling it shareable, skim the output for client data that isn't a credential (customer names, internal URLs). The tool doesn't remove those, and it's the user's call.

## What it includes and leaves out

- **In:** prompts, including ones sent mid-turn (labelled); Claude's text answers; one line per tool call; answers to Claude's multiple-choice questions; a list of files written and links mentioned.
- **Out:** thinking, tool output, screenshots (noted as attached), subagent transcripts, the summary written after context compaction, system reminders, and relayed subagent reports.
- **Masked:** the home directory becomes `~`. Atlassian, GitHub, Slack, AWS, Anthropic/OpenAI and Grafana tokens, private keys and JWTs are masked, as is any `*_TOKEN=`, `*_SECRET=`, `*PASSWORD=` or `*API_KEY=` value. `$VAR` references are left alone.

It reads Claude Code's session JSONL, which is undocumented and changes between releases. If prompts go missing or tool calls show up as text, the record shapes have moved. Fix `events()` in `bin/session-export`.
