---
name: tracker-page
description: Keep a live, local HTML status page for a long multi-step task — one status.json drives a page with phases, statuses, progress bar, blockers, decisions, clickable links and an append-only log, served on localhost and refreshed after every change. Also builds side-by-side review pages (before/after, Approve/Hold, "Summary for Claude") with a status board driven by an approvals file. Use for "track this in an HTML page", "give me a status page", "tracker on localhost", "a way to review when I'm back", "review page", "side-by-side diff for each item", a /goal or long agent run that needs a visible status, or any work where the human reviews many items and approves them in batches.
---

# Live tracker page

A long task is easier to follow, hand over and resume when its state lives in a file the human can open at any time. The pattern: **one JSON file is the source of truth, a script renders it to HTML, a local server shows it, and every state change updates the JSON and re-renders.** The page is a projection; never hand-edit the HTML.

Two tools, usable separately or together:

| Script | Input | Output | For |
|---|---|---|---|
| `scripts/tracker.py` | `<dir>/status.json` | `<dir>/index.html`, `<dir>/LOG.md` | the task itself: items, phases, statuses, blockers, decisions, links, log |
| `scripts/review.py` | `cards.json` (+ `approvals.json`) | one page per group + a status board | reviewing many pieces of content (cells, sections, files) before they are published |

Scripts live in this skill's folder: `S=~/.claude/skills/tracker-page/scripts`. Python 3 stdlib only.

## Setting up a tracker

Pick a folder inside the project (e.g. `<repo>/tracker/` or `<repo>/<area>/final-review/`), so the page, data and reports are versioned with the work.

```bash
python3 $S/tracker.py init  <dir> --title "Final review" --subtitle "Source list: TODOs.md"
python3 $S/tracker.py item  <dir> 1 --phase "Phase 0 — Sources" --title "Case studies final" --status in-progress --note "Agent D drafting; see reports/03.md"
python3 $S/tracker.py link  <dir> "Review Sheet=https://docs.google.com/..." "Run log=LOG.md"
python3 $S/tracker.py serve <dir> --port 8765        # run in the background; tell the human the URL
```

Statuses: `todo` · `in-progress` · `review` (ready for the human) · `decision` (the human must choose) · `blocked` · `done`. Every item can carry `--rev` (the commit, version, PR or Sheet revision that moved it) and `--link LABEL=URL`.

Give the human a one-line restart command for after a reboot. The server is a foreground process, so it dies with the session that started it.

**Markdown opens formatted.** Relative `.md` links (in notes, item links, top links and the log) are rendered as `/md?p=<path>`. `serve` starts one `mdserve` per folder the first time a file there is opened, redirects to it, and stops those servers when it exits. Because mdserve only serves a flat folder, each folder gets its own. Paths may climb out of the tracker folder (`../../docs/x.md`) but must stay inside the git repo that holds it. Without mdserve on `PATH`, or with `--no-mdserve`, the file is served as plain text. Link markdown by relative path, never as `file://` or a fixed mdserve port: the ports change on every start.

## Rules that make the page worth keeping open

1. **Update after every state change, not at the end.** Each agent landing, push, approval or decision → `tracker.py item …` (status, note, rev) and a `tracker.py log "…"` line. The page reloads itself every 30 s.
2. **Link everything.** Notes and log lines are linkified automatically: http(s) URLs, and relative paths to files that exist in the tracker folder (reports, CSVs, PDFs). Put reports next to `status.json` so their paths become links. Put the external surfaces (Sheets, PRs, Drive and Box folders) in `tracker.py link`.
3. **Blockers and decisions are separate panels.** `tracker.py block "…"` for what stops the work, `tracker.py ask "…"` for what only the human can decide. Clear them with `--clear` when resolved, and record the resolution in the item note and the log.
4. **The log is append-only and uses the real clock.** `tracker.py log` stamps the system time. Never write times from memory; if one was wrong, append a correction rather than editing history.
5. **Leave a "pick up here" note.** When pausing or handing over, write a short `REVIEW-WHEN-BACK.md` (or similar) in the tracker folder: where to look, what's done, what's blocked, the numbered next steps. Link it from the page.
6. **Never claim more than the data shows.** The page's numbers come from the JSON. If something isn't verified, the note says so.

## Review pages: side by side, approve in batches

Use when the human must review many pieces of content before they go anywhere: workbook cells, document sections, generated files.

1. Write `cards.json`: groups of cards, each with `id`, `heading`, optional `context` (the requirement), `before`, `after` and optional `links`. Group the way the human will review (per customer, per chapter).
2. `python3 $S/review.py build cards.json <dir>/cells --approvals <dir>/approvals.json`
3. The human opens a group page. Each card shows **before on the left and after on the right, full text on both sides**, with removed words in red and added words in green. Side by side is the default because restructured text makes inline diffs unreadable; an inline diff sits behind a toggle.
4. The human clicks Approve or Hold, adds notes, then **Summary for Claude**, and pastes the result into the session.
5. Save the pasted summary to a file and run `python3 $S/review.py record <dir>/approvals.json summary.txt`, then rebuild. Approved cards get a ✅ badge, and the board's approved/held/pending counts come from `approvals.json`, never from the browser.
6. **Publish only what's approved,** and only the cells that changed: diff the approved set against the live destination and push the difference. Then re-download and confirm zero remaining differences. Fix held cards, show them again, repeat.

## Colours and layout (keep them)

- **Tokens on `:root`:** ink, mute, line, accent blue, ok green, warn amber, question red, insert green, delete red. Dark mode via `prefers-color-scheme`.
- **Status icons:** ✅ ⬜ ⏳ ❓ ⛔ · plus coloured labels. Phase header rows show done/total.
- **Cards:** rounded corners and thin borders, with green borders on approved cards and red on held ones. Wide pages (1500 px) for side by side, stacking below 800 px.
- These live in `THEME` in `tracker.py`; `review.py` reuses them, so both pages look like one system.

## Don'ts

- Don't let the HTML and the JSON drift. Always regenerate.
- Don't keep approval state only in the browser. `localStorage` is a convenience; `approvals.json` is the record.
- Don't publish a whole render over a live document the human edits by hand. Push only the changed, approved cells.
