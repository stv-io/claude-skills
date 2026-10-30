# mac-disk-cleanup

**macOS only. When your Mac's disk is full, Claude finds what's using the space and frees it one step at a time. Nothing is deleted until you approve it, and every step's real effect on free space is measured.**

```mermaid
flowchart TD
  A["measure.sh: read-only baseline (APFS containers, free space, snapshots, biggest folders)"] --> B["Claude proposes candidates, biggest first, by tier: caches · tool data · personal files · git"]
  B --> C{"You approve this step?"}
  C -- no --> B
  C -- yes --> D["run_step.py: free space before"]
  D --> E{"--delete target allowed? not a symlink · inside your home folder · not a protected folder"}
  E -- refused --> F["Logged as blocked"]
  E -- allowed --> G["Run the clean command or delete"]
  G --> H["Free space after: the measured change"]
  H --> I["Tracker item and log updated"]
  I --> B
```

Disk cleanups go wrong in three ways: deleting something you wanted, killing something that was running, or reporting space that never came back. This skill measures first, agrees each step with you at the right level (one approval can cover a batch of caches; personal files are always one at a time), runs one step at a time, and checks the real change with `df`. It knows the usual developer hotspots and their own clean commands: uv, npm, Homebrew, Nix, Colima/Docker, Terraform providers, duplicate git clones. It also explains why freed space can stay "missing" until a Time Machine local snapshot clears.

## Install

Install it with [tracker-page](../tracker-page), which shows the run as it happens:

```bash
npx skills add stv-io/claude-skills --skill mac-disk-cleanup --skill tracker-page -g
```

## What you need

- **macOS.** It stops on anything else.
- **[dust](https://github.com/bootandy/dust)** for fast folder sizes: `brew install dust`. Check: `dust --version`.
- **Python 3.**

## Use it

*"My disk is full"*, *"free up space"*, *"what's using my disk?"*. If a command fails with "No space left on device", Claude offers this skill. It doesn't start a cleanup on its own.

## What it touches

- **Reads** disk usage across your home folder, `/Applications`, `/opt/homebrew` and `/private/var` (sizes only).
- **Writes** a run folder at `~/disk-cleanup-tracker/runs/<date>/` (reports, results, the tracker page).
- **Deletes** only what you approve, step by step. Its `--delete` helper refuses symlinks, anything outside your home folder, and these folders themselves: `~`, `~/Library`, `~/Library/Application Support`, `~/Library/Caches`, `~/Documents`, `~/Desktop`, `~/Downloads`, `~/Pictures`, `~/code`, `~/.cache`, `~/.local`, `~/.local/share`, `~/.config`, `~/.ssh`. Approved clean commands (such as `uv cache clean` or `brew cleanup`) run as they are.
- **Never** uses `sudo` itself. When a step needs it (deleting a local snapshot), Claude gives you the exact command to run.
- **Network:** none from the skill. Some clean commands, such as `brew cleanup`, may contact their own servers.

## Limits

- Free space comes back only after macOS releases it. A local snapshot can hold deleted files for up to a day.
- Measurements taken while other things are writing to disk are noisy. Claude says so.

## Update or remove

```bash
npx skills update mac-disk-cleanup -g
npx skills remove mac-disk-cleanup -g    # run folders under ~/disk-cleanup-tracker stay until you delete them
```
