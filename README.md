# claude-skills

A few Claude Code skills I use daily. MIT licensed.

| Skill | What it does | Needs |
|---|---|---|
| [tracker-page](skills/tracker-page) | A live local HTML status page for long agent tasks, driven by one `status.json`. Also builds side-by-side review pages with Approve/Hold and an approvals file. | Python 3 (stdlib only); optional: [mdserve](https://github.com/jfernandez/mdserve), [crit](https://crit.md/) |
| [browser-select](skills/browser-select) | Maps friendly names (`dia-work`, `chrome-personal`, …) to the deviceIds the Claude in Chrome MCP tools need, and makes Claude ask which browser to use instead of guessing. Ships the `browsers` CLI. | Python 3, the Claude in Chrome extension |
| [claude-usage](skills/claude-usage) | Lets Claude check your plan's 5-hour and weekly usage before launching anything expensive. Ships `claude-usage` (reader) and `claude-usage-capture` (writer, fed by your status line). | bash, jq ≥ 1.6, a status-line command |
| [mac-disk-cleanup](skills/mac-disk-cleanup) | Finds what is filling a Mac's disk and frees space one agreed step at a time: baseline with `dust`, a catalogue of developer hotspots (uv, npm, Nix, Colima, Terraform providers, git) with their native clean commands, measured before/after steps, local-snapshot reclaim, all logged in a tracker page. | Python 3, `dust`, [tracker-page](skills/tracker-page) |

## Install

The skills expect to live at `~/.claude/skills/<name>`. Symlink them:

```bash
git clone https://github.com/stv-io/claude-skills.git ~/code/claude-skills
for s in tracker-page browser-select claude-usage mac-disk-cleanup; do
  ln -s ~/code/claude-skills/skills/$s ~/.claude/skills/$s
done
# Codex reads skills from ~/.codex/skills as well
ln -s ~/code/claude-skills/skills/mac-disk-cleanup ~/.codex/skills/mac-disk-cleanup
# CLIs on your PATH
ln -s ~/code/claude-skills/skills/browser-select/bin/browsers        ~/bin/browsers
ln -s ~/code/claude-skills/skills/claude-usage/bin/claude-usage      ~/.local/bin/claude-usage
ln -s ~/code/claude-skills/skills/claude-usage/bin/claude-usage-capture ~/.local/bin/claude-usage-capture
```

### tracker-page: optional tools

Neither is required; the page works without them.

```bash
brew install mdserve   # linked .md files open formatted instead of as plain text
brew install crit      # inline comments on a served tracker or review page: crit http://localhost:8765
```

### claude-usage: feed it from your status line

Claude Code passes `rate_limits` only to the status-line command. Add one line to yours (see `statusLine` in `~/.claude/settings.json`):

```bash
input=$(cat)
printf '%s' "$input" | claude-usage-capture   # writes ~/.claude/usage-cache.json
# ...the rest of your status line...
```

The cache refreshes only while an interactive session is open.

### browser-select: register your browsers

The registry lives at `~/.claude/browsers.json`, outside this repo. Bind each browser while it is connected:

```bash
browsers help-register
```
