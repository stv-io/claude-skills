---
name: tracker-page
description: Keep a live, local HTML status page for a long multi-step task — one status.json drives a page with phases, statuses, progress bar, filters, blockers, decisions, clickable links, an activity timeline and per-item comments the human can leave for later (saved to feedback.json), served on localhost and refreshed after every change. Also builds side-by-side review pages (before/after, Approve/Hold, "Summary for Claude") with a status board driven by an approvals file. Use for "track this in an HTML page", "give me a status page", "tracker on localhost", "a way to review when I'm back", "review page", "side-by-side diff for each item", a /goal or long agent run that needs a visible status, or any work where the human reviews many items and approves them in batches.
---

# Live tracker page

A long task is easier to follow, hand over and resume when its state lives in a file the human can open at any time. The pattern: **one JSON file is the source of truth, a script renders it to HTML, a local server shows it, and every state change updates the JSON and re-renders.** The page is a projection; never hand-edit the HTML.

Two tools, usable separately or together:

| Script | Input | Output | For |
|---|---|---|---|
| `scripts/tracker.py` | `<dir>/status.json` | `<dir>/index.html`, `<dir>/LOG.md`, `<dir>/feedback.json` | the task itself: items, phases, statuses, blockers, decisions, links, log, the human's comments |
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

Give the human a one-line restart command for after a reboot. The server is a foreground process, so it dies with the session that started it. **Restart `serve` after the skill's scripts change:** a running server keeps the old code, so the page (re-rendered by the new script) can't save comments until it restarts. The page says so.

**Markdown opens formatted.** Relative `.md` links (in notes, item links, top links and the log) are rendered as `/md?p=<path>`. `serve` starts one `mdserve` per folder the first time a file there is opened, redirects to it, and stops those servers when it exits. Because mdserve only serves a flat folder, each folder gets its own. Paths may climb out of the tracker folder (`../../docs/x.md`) but must stay inside the git repo that holds it. Without mdserve on `PATH`, or with `--no-mdserve`, the file is served as plain text. Link markdown by relative path, never as `file://` or a fixed mdserve port: the ports change on every start.

**Optional tools.** Both are optional; the scripts themselves need only Python 3.
- `mdserve` (`brew install mdserve`): formatted markdown, as above.
- `crit` (`brew install crit`): when the human wants to comment on the page itself while you wait, run `crit http://localhost:<port>` in the background and act on the comments when it returns. If `crit` isn't installed, ask the human to paste their comments instead.

## Rules that make the page worth keeping open

1. **Update after every state change, not at the end.** Each agent landing, push, approval or decision → `tracker.py item …` (status, note, rev) and a `tracker.py log "…"` line. While served, the page checks for changes every 15 s and reloads only when something changed and no comment is being typed.
2. **Link everything.** Notes and log lines are linkified automatically: http(s) URLs, and relative paths to files that exist in the tracker folder (reports, CSVs, PDFs). Put reports next to `status.json` so their paths become links. Put the external surfaces (Sheets, PRs, Drive and Box folders) in `tracker.py link`.
3. **Blockers and decisions are separate panels.** `tracker.py block "…"` for what stops the work, `tracker.py ask "…"` for what only the human can decide. Clear them with `--clear` when resolved, and record the resolution in the item note and the log.
4. **The log is append-only and uses the real clock.** `tracker.py log` stamps the system time in UTC. Never write times from memory; if one was wrong, append a correction rather than editing history.
5. **Leave a "pick up here" note.** When pausing or handing over, write a short `REVIEW-WHEN-BACK.md` (or similar) in the tracker folder: where to look, what's done, what's blocked, the numbered next steps. Link it from the page.
6. **Never claim more than the data shows.** The page's numbers come from the JSON. If something isn't verified, the note says so.
7. **Read the human's comments before every step, and wait for them when idle.** Run `tracker.py feedback <dir>` before each step. Whenever you stop to wait for the human, start `tracker.py feedback <dir> --wait` in the background: it ends, and wakes you, when they press **Send to Claude**, and prints what they sent. For each comment, act on it (or say why not), then `tracker.py feedback <dir> --resolve ID --reply "what you did"`; the reply shows under the comment on the page. Then start `--wait` again. Comments are how the human steers the run from the page, so they come before continuing the plan.

## Comments the human leaves for later

Every item has a **Comment** button, and the sidebar takes general comments. With `serve` running, **Save comment** writes to `<dir>/feedback.json` straight away and re-renders, so comments survive closing the browser and outlive the session. The human can write several, then press **Send to Claude** in the sidebar. That stamps them `sent_at`, and a running `feedback --wait` hands them over and stamps `delivered_at`. Each comment shows its stage: *saved, not sent yet* → *sent to Claude* → *seen by Claude* → *resolved* (with the reply). Unsent comments still show in `tracker.py feedback`, so nothing is lost if the human forgets to press Send. The **Comments** tab lists items with open comments. `feedback.json` is append-only: nothing is deleted.

If the page can't save, it says why and copies the comment to the clipboard for pasting into the session. The reasons are: opened as a file, served by an older `tracker.py` that needs a restart, or the server isn't responding. The server accepts JSON posts from its own origin only, so another website can't post comments into the tracker.

## Review pages: side by side, approve in batches

Use when the human must review many pieces of content before they go anywhere: workbook cells, document sections, generated files.

1. Write `cards.json`: groups of cards, each with `id`, `heading`, optional `context` (the requirement), `before`, `after` and optional `links`. Group the way the human will review (per customer, per chapter).
2. `python3 $S/review.py build cards.json <dir>/cells --approvals <dir>/approvals.json`
3. The human opens a group page. Each card shows **before on the left and after on the right, full text on both sides**, with removed words in red and added words in green. Side by side is the default because restructured text makes inline diffs unreadable; an inline diff sits behind a toggle.
4. The human picks Approve, Hold or Not reviewed on each card (or uses the keys: `j`/`k` move, `a` approve, `h` hold, `u` not reviewed, `n` note), adds notes, then **Copy summary for Claude**, and pastes the result into the session. Unchanged cards are folded away at the bottom with **Approve all unchanged**; **Next unreviewed** jumps to the next card still open.
5. Save the pasted summary to a file and run `python3 $S/review.py record <dir>/approvals.json summary.txt`, then rebuild. Cards recorded as approved or held get a label, and the board's approved/held/pending counts come from `approvals.json`, never from the browser.
6. **Publish only what's approved,** and only the cells that changed: diff the approved set against the live destination and push the difference. Then re-download and confirm zero remaining differences. Fix held cards, show them again, repeat.

## Look and feel (keep it)

- **One stylesheet, `scripts/theme.css`,** inlined into every page by both scripts, so each page works as a standalone file and both look like one system. The style follows GitHub's Primer: boxes with a grey header row, outlined status labels, counters on filter tabs, a timeline for activity. Light and dark via `prefers-color-scheme`.
- **Status is never colour alone:** each item has an SVG icon with an `aria-label`, a text label and a colour.
- **Tracker:** a progress bar split by status, flash panels for blockers and decisions, a box per phase (folded once all its items are done), and a sidebar with recent activity and comments. The tab title starts with the number of items that need the human.
- **Review:** wide pages (1500 px) for side by side, stacking below 800 px. Approved cards get a green border, held ones a red border.
- Page-specific CSS sits next to the markup in each script; add shared pieces to `theme.css`.

## Don'ts

- Don't let the HTML and the JSON drift. Always regenerate.
- Don't keep approval state only in the browser. `localStorage` is a convenience; `approvals.json` is the record.
- Don't edit or delete entries in `feedback.json`. Resolve them with a reply.
- Don't publish a whole render over a live document the human edits by hand. Push only the changed, approved cells.

## Changing the scripts

Tests live in `tests/` and need nothing installed beyond `uv`:

```bash
cd ~/.claude/skills/tracker-page/tests
uv run --with pytest --with playwright playwright install chromium   # once
uv run --with pytest --with playwright pytest -q
```

They cover the helpers, rendering, the feedback file and CLI, the server's `/md` and `/feedback` routes (including refused requests), the review round trip, and the pages' JavaScript in headless Chromium in light and dark mode. The scripts must keep running on macOS's system Python 3.9: no 3.10+ syntax, and no nested f-strings that reuse the outer quote. A test compiles them with `/usr/bin/python3`.
