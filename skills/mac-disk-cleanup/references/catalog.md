# Hotspot catalogue

One entry per place space usually hides on a developer Mac. Each entry: where it is, how to measure it, the tool's own clean command, what to check first, what breaks, and what to do afterwards. Add an entry (or a line to one) whenever a run teaches something new.

Sizes are what `dust` reports as allocated. They are not a promise of free space: APFS clones, hardlinks and local snapshots all keep blocks alive.

## Always: local snapshots

- **Check:** `tmutil listlocalsnapshots /`
- **Why:** a Time Machine local snapshot taken before a deletion keeps every deleted block. Free space stays flat until it goes. In the run this was written from, deleting one snapshot moved free space from 176 to 321 GiB.
- **Clean:** `sudo tmutil deletelocalsnapshots <YYYY-MM-DD-HHMMSS>`. This needs sudo; hand it to the user as `! sudo …`. macOS also thins snapshots on its own within about 24 h, or sooner when space is low.

## Tier A: regenerable caches (batch approval is fine)

| Cache | Path | Clean | Check first / aftercare |
|---|---|---|---|
| **uv** | `~/.cache/uv` | `uv cache clean` (or `uv cache prune` for unused entries only) | Blocks while any uv/uvx process runs, and MCP servers are often uvx processes. Stop them (`pgrep -fl uv`), never `--force`. Afterwards run `/mcp` → reconnect in each session; the first start downloads again. Can be 90+ GiB. |
| **npm** | `~/.npm` | `npm cache clean --force` | `EACCES` means root-owned files from an old `sudo npm`: `! sudo chown -R $(id -u):$(id -g) ~/.npm`, then retry. Keep `_npx` entries that running processes use. |
| **Homebrew** | `~/Library/Caches/Homebrew` | `brew cleanup --prune=all` | `brew cleanup -n` shows the size first. |
| **Terragrunt** | `~/Library/Caches/terragrunt` | `rm -rf` the folder | No terragrunt running. |
| **Terraform plugin cache** | `~/.terraform.d/plugin-cache` | `rm -rf` the contents | Only if `TF_PLUGIN_CACHE_DIR` points there. |
| **Yarn / pnpm** | `~/Library/Caches/Yarn`, `~/Library/pnpm` | `yarn cache clean`, `pnpm store prune` | |
| **trivy** | `~/Library/Caches/trivy` | `trivy clean --all` | The DB downloads again on the next scan. |
| **Browser automation** | `~/Library/Caches/ms-playwright`, `~/.cache/puppeteer` | `rm -rf` | The next run downloads browsers again. |
| **Browsers** | `~/Library/Caches/{Google,Dia,Comet,…}` | Clear from inside the browser, or `rm -rf` with the browser quit | |
| **Spotify** | `~/Library/Caches/com.spotify.client` | Settings → Storage → Clear cache | Offline downloads are separate. Set a cache limit there too. |
| **huggingface** | `~/.cache/huggingface` | `hf cache delete` (interactive) | Models are lost offline. Closer to tier C if used. |

## Tier B: tool data with side effects (one at a time)

**Nix store** (its own APFS volume, "Nix Store")
- **Clean:** `nix-collect-garbage -d`, plus `sudo nix-collect-garbage -d` for the system profile.
- **Side effects:** current roots are kept; old generations are deleted, so rollback is lost.
- **In practice:** freed 54.6 GiB in one run.

**Colima / Docker** (`~/.colima/_lima/<profile>/diffdisk`; the host file grows and does not shrink on its own)
1. Measure: `docker system df`, then `colima ssh -- sudo du -xh -d1 /var/lib`.
2. Look for leaked containers: `docker ps -a --format '{{.Image}}' | sort | uniq -c`. MCP servers launched with `docker run` and no `--rm` pile up one set per session.
3. Lightest option: `docker container prune`, `docker image prune -a`, `docker volume prune`, then `colima ssh -- sudo fstrim -av` so the host file can shrink.
4. Heaviest option, only if the user chooses it: `colima delete` and start again. This wipes all images, volumes and data; MCP images are pulled again.

**Terraform/OpenTofu provider binaries in projects**
- **Where:** `.terraform` and `.terragrunt-cache` under the code folders.
- **Clean:** `scripts/provider_binaries.py scan ~/code out.json`, review, then `… delete out.json`. Only provider binaries are touched; state and `.terraform.lock.hcl` stay.
- **Aftercare:** every project needs `init` before its next plan.
- **Prevent:** set `TF_PLUGIN_CACHE_DIR` so projects share one copy. 25 GiB in one run.

**Project dependencies and build output** (`node_modules`, `target`, `build`, `.venv`)
- **Check:** only folders that are git-ignored and contain zero tracked files (`git ls-files <dir> | head -1` is empty). Prefer inactive projects.
- **Never** run a blanket `find -name build -exec rm`: `vendor/`, `build/` and `env/` often hold tracked source.

**Updater / app-version backups** (e.g. `~/.local/share/updater/backups`)
- Old app versions kept for rollback; delete once you are happy with the current versions.

**Claude desktop VM** (`~/Library/Application Support/Claude/vm_bundles`, ~10 GiB)
- The sandbox VM image. It downloads again when the feature is used.

## Tier C: personal data (one at a time, always ask)

**Downloads**
- Installers for apps already in `/Applications` (`.dmg`, `.zip`, `.pkg`, `.iso`) and stale `.crdownload` files are the safe part.
- Media and documents are the user's call.

**Local LLM models** (`~/.lmstudio/models`, `~/.ollama/models`)
- List each model with its size and last-used date (`stat -f %Sa`). Remove from inside the app.

**VMs** (`~/Virtual Machines.localized`, VMware/UTM/Parallels folders, `~/Library/Application Support/<app>/VM`)
- Report the last-used date of the `.vmx` or disk file. Installer ISOs next to them are usually safe to remove.

**Media, photos, project folders**
- Report sizes only. Do not suggest deleting them.

## Tier D: git hygiene (one at a time, needs evidence)

**Duplicate clones** (same origin, separate `.git`)
- **Check:** `scripts/git_redundancy.py clone <candidate> <keeper>` must say SAFE TO DELETE: no changes, stashes or worktrees, every ref, HEAD and reflog commit exists in the keeper, and no process is inside.
- **Before deleting:** mention the ignored files it lists (`.env`, outputs), because git does not hold them.

**Linked worktrees**
- **Remove** with `git worktree remove <path>`. Never `rm` a worktree or its parent checkout.

**Large `.git`** (loose objects)
1. `git gc --prune=never` packs everything and deletes nothing (3.5 → 2.2 GiB in one run).
2. Then `scripts/git_redundancy.py unreachable <repo>` shows what is left. Usually it's unreachable commits, such as auto-"Checkpoint" commits from an editor or agent.
3. `git gc --prune=now` drops them permanently, and only after the user has seen that summary.

## Not worth the effort

- `/Applications`, `/private/var/folders` and `/private/var/db`: managed by the system, or small wins.
- Homebrew Cellar: `brew cleanup` already covers the old versions.
