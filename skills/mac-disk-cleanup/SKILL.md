---
name: mac-disk-cleanup
description: macOS only. Find what is filling a Mac's disk and free space safely, one agreed step at a time, with every step measured and logged in a live tracker page. Use for "disk space notification", "my disk is full", "free up space", "what's using my disk", "clean up caches", "/mac-disk-cleanup". When a tool fails with "No space left on device", offer this skill rather than starting a cleanup unasked. Covers APFS containers, Time Machine local snapshots, developer caches (uv, npm, Homebrew, Terraform/Terragrunt, Nix, Colima/Docker), project build output, duplicate git clones, models, VMs and Downloads.
---

# Mac disk cleanup

A disk cleanup goes wrong in three ways: deleting something the user wanted, killing something that was running, or reporting space that never came back. This skill avoids all three:
- **measure** before anything else;
- **agree** each step at the right level;
- **run** one step at a time, measuring free space before and after;
- **log** the step.

The hotspot list, with clean commands and gotchas, is in `references/catalog.md`. Read it before you propose cleanups. Scripts: `S=<this skill's folder>/scripts` (`~/.claude/skills/mac-disk-cleanup` for a global install, `.claude/skills/mac-disk-cleanup` in a project).

## 0. Before touching anything

- **macOS only.** If `uname -s` isn't `Darwin`, say so and stop; `measure.sh` refuses too. Check `dust` is installed (`brew install dust`).
- **Is a cleanup already running?** Look for another agent (Claude, Codex) or a terminal running one: `pgrep -fl 'uv cache|nix-collect-garbage|brew cleanup|npm cache'`, and look for a recent run folder under `~/disk-cleanup-tracker/runs/`. If you find one, join that tracker and log there. Don't start a second one.
- **Run the baseline:** `bash $S/measure.sh ~/disk-cleanup-tracker/runs/$(date +%F)`. It is read-only and reports:
  - which APFS container is full (the internal one is usually `disk3`; an external backup disk is a different container);
  - free space;
  - local snapshots;
  - the biggest folders, measured with `dust`.

  Use `dust` or `dua`, never `du -sh ~`; `du` takes minutes on a large home folder.
- **Less than ~5% free is urgent.** Say so, and offer tier A caches first: they are the fastest safe win.

## 1. Answer and propose

Tell the user which disk it is, then list candidates biggest first, grouped by tier:

| Tier | What | Approval |
|---|---|---|
| A | Caches that rebuild themselves | one approval can cover the batch |
| B | Tool data with side effects (Nix, Colima, provider binaries, build output) | one at a time, side effects stated first |
| C | Personal data (Downloads, models, VMs, media) | one at a time, always; give sizes and last-used dates; never push |
| D | Git (duplicate clones, `gc`) | one at a time, with the evidence from `git_redundancy.py` |

For each candidate give: size, the exact command, what breaks or must happen afterwards, and whether it can be undone. Use GiB, and label any size that comes from an earlier estimate rather than a fresh measurement.

## 2. Tracker

Use the [`tracker-page`](../tracker-page) skill (same repo; install it alongside this one) in the run folder: one item per candidate, grouped by tier. Items move from `review`, to `decision` (waiting for the user), to `in-progress`, to `done` or `blocked`. Start `tracker.py serve` in the background and give the user the URL. Log every approval in the user's words: `tracker.py log "User selected …"`.

## 3. Run one step at a time

- Run each agreed step with `python3 $S/run_step.py <run-dir> <item> -- <command…>`. For plain deletions use `--delete <paths…>`. `--delete` refuses symlinks, paths outside `$HOME`, and these folders themselves: `~`, `~/Library`, `~/Library/Application Support`, `~/Library/Caches`, `~/Documents`, `~/Desktop`, `~/Downloads`, `~/Pictures`, `~/code`, `~/.cache`, `~/.local`, `~/.local/share`, `~/.config`, `~/.ssh` (things inside them can still be deleted once approved).
- It records `df -k` before and after, the output, the exit code, `results.jsonl`, and updates the tracker item and log.
- **Before each step,** run that item's preflight from the catalogue: running processes, open files, git reachability. Re-check the scope right before deleting, not just when you proposed it.
- **Stop owning processes gracefully,** and only the ones that block the step. Tell the user what will disconnect: for example, uv-launched MCP servers drop until `/mcp` reconnect.
- **If a command is denied or needs sudo,** log the exact error and hand the user a ready line: `! sudo …`. Never edit permission settings yourself.
- **If a step fails,** log it and keep it `blocked`. Don't fall back to `rm -rf` on something that has its own clean command.

## 4. Get the space back

When a step shows little or no free-space gain, check local snapshots: `tmutil listlocalsnapshots /`.
- If a snapshot was taken before the deletions, it holds the deleted blocks. Give the user `! sudo tmutil deletelocalsnapshots <date>` (or tell them it clears itself within about a day).
- Re-measure afterwards with `df -k` and log the real number. If a shell wrapper or hook filters `df` output, check the Avail column survived.

## 5. Close the run

- **Summary table:** each item, its status, and the measured change in free space; the total, from the baseline to now.
- **Prevention:**
  - `TF_PLUGIN_CACHE_DIR`;
  - `--rm` on MCP `docker run` lines;
  - a Spotify cache limit;
  - `uv cache prune` now and then;
  - asking before large downloads land in Downloads.
- **Handover:** write `REVIEW-WHEN-BACK.md` in the run folder with the open decisions.
- **Catalogue:** tell the user about any new lesson (new hotspot, new failure, new command) so it can go into `references/catalog.md` upstream. Don't edit the installed copy: `npx skills update` replaces it. In a clone of the repo, edit the file there.

## Rules

- **Nothing gets deleted without approval at its tier.** An approval in one run doesn't carry over to the next.
- **Free space is measured, never inferred from folder sizes.** Measurements taken while other things are running are noisy; say so.
- **Times:** chat follows the user's time convention from their CLAUDE.md, if any. Logs and reports use the system clock and are append-only; fix a mistake by adding a correction, never by editing history.
- **Personal data:** report it, don't judge it. Offer, never push.
