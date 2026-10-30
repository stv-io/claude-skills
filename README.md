# claude-skills

Five Claude Code skills I use every day: a live status page for long agent runs, and the chores around them. MIT licensed.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/tracker-page-dark.png">
  <img alt="tracker-page: a live status page with a progress bar, blocked and decision panels, phases of items with statuses, and a recent-activity timeline." src="assets/tracker-page.png">
</picture>

## Skills

| Skill | What it solves | Platform | Needs | Touches |
|---|---|---|---|---|
| [tracker-page](skills/tracker-page) | Long agent runs lose their state in the chat. Claude keeps it in one file and shows it as a live page on localhost, with comments you can leave for later. | macOS, Linux | Python 3 | writes a tracker folder in your project; serves 127.0.0.1 |
| [mac-disk-cleanup](skills/mac-disk-cleanup) | A full disk, cleaned one approved and measured step at a time. **Deletes files after you approve each step.** | **macOS only** | Python 3, [dust](https://github.com/bootandy/dust), tracker-page | writes `~/disk-cleanup-tracker/`; deletes what you approve |
| [session-export](skills/session-export) | Share a Claude Code session as clean Markdown, not a terminal dump. Credential masking is best-effort. | any | Python 3 | reads your session transcripts; writes the file you name |
| [claude-usage](skills/claude-usage) | Claude checks your 5-hour and weekly plan usage before starting something expensive. **Needs a one-line status-line hook.** | macOS, Linux | bash, jq 1.6+ | writes `~/.claude/usage-cache.json` |
| [browser-select](skills/browser-select) | With several browsers connected to Claude in Chrome, Claude asks which one instead of acting in the wrong account. | any | [Claude in Chrome](https://claude.com/chrome) in 2+ browsers, Python 3 | writes `~/.claude/browsers.json` |

None of them use the network themselves.

## Install (30 seconds)

```bash
npx skills add stv-io/claude-skills
```

It asks which skills and which agents to install for. Without `-g` they go into the current project (`.claude/skills/`); with `-g` into `~/.claude/skills/` for every project. To install one directly:

```bash
npx skills add stv-io/claude-skills --skill session-export -g
```

Two skills need a minute of setup after installing: [claude-usage](skills/claude-usage#set-up-the-status-line-hook-once) (a status-line hook) and [browser-select](skills/browser-select#set-up-name-your-browsers-once) (name your browsers). Each skill's README lists what it needs, with install and check commands.

## Update or remove

```bash
npx skills update -g                        # all skills installed with -g
npx skills remove session-export -g         # one skill
```

## What they do

### tracker-page

A live local page for a long task, driven by one `status.json` that Claude updates after every step: phases, statuses, blockers, decisions for you, links, an activity log. Leave comments on any item and press **Send to Claude**. It also builds side-by-side review pages (before/after, Approve/Hold) for approving content in batches. [Read more →](skills/tracker-page)

### mac-disk-cleanup

Measures first, proposes candidates biggest-first by risk tier, and asks before every step (personal files always one at a time). Each step's real gain is measured with `df` and logged in a tracker page. It knows the usual developer hotspots and their own clean commands, and it refuses to delete symlinks, anything outside your home folder, or top-level folders like `~/Documents`. [Read more →](skills/mac-disk-cleanup)

### session-export

Numbered prompts, Claude's original answers, one line per tool call, a contents list and outcomes, for the whole session or a range of prompts. Home paths and common token formats are masked. Read the file before you share it. [Read more →](skills/session-export)

### claude-usage

Your status line saves the plan's rate limits to a cache; the skill reads it, so Claude can tell you "5h: 44%, resets 15:10" and ask before launching a big fan-out when you're close to a limit. [Read more →](skills/claude-usage)

### browser-select

Gives each connected browser a name you choose (`work-chrome`, `personal-dia`), makes Claude ask which one to use when you haven't said, and keeps your answer for the session. [Read more →](skills/browser-select)

## Hacking on these

To edit the skills and have changes take effect immediately, clone the repo and symlink the folders instead of installing copies:

```bash
git clone https://github.com/stv-io/claude-skills.git ~/code/claude-skills
for s in tracker-page browser-select claude-usage session-export mac-disk-cleanup; do
  ln -s ~/code/claude-skills/skills/$s ~/.claude/skills/$s
done
# Optional: put the CLIs on your PATH
ln -s ~/code/claude-skills/skills/browser-select/bin/browsers           ~/.local/bin/browsers
ln -s ~/code/claude-skills/skills/claude-usage/bin/claude-usage         ~/.local/bin/claude-usage
ln -s ~/code/claude-skills/skills/claude-usage/bin/claude-usage-capture ~/.local/bin/claude-usage-capture
ln -s ~/code/claude-skills/skills/session-export/bin/session-export     ~/.local/bin/session-export
```

Don't run `npx skills add` over these symlinks: it replaces them with copies without asking.

tracker-page has tests (`uv` is all you need); see [its SKILL.md](skills/tracker-page/SKILL.md#changing-the-scripts).

## License

[MIT](LICENSE)
