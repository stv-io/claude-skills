#!/usr/bin/env python3
"""Run one agreed cleanup step and record what it actually freed.

    run_step.py <run-dir> <item-id> -- <command> [args...]
    run_step.py <run-dir> <item-id> --delete <path> [<path> ...]

Captures free space (df -k) before and after, saves output and exit code to
reports/, appends results.jsonl, and updates the tracker item and log.
--delete removes the named paths after refusing symlinks, anything outside
$HOME, and top-level folders such as ~/Library or ~/code.
"""
import datetime
import json
import os
import pathlib
import shutil
import subprocess
import sys

HOME = pathlib.Path.home().resolve()  # resolved, so targets (also resolved) compare correctly when $HOME has a symlink in it
# tracker-page is a sibling skill: next to this one as installed, in the repo it links to, or in ~/.claude/skills
HERE = pathlib.Path(__file__).absolute().parent
TRACKER = next((p for p in (HERE.parent.parent / "tracker-page/scripts/tracker.py",
                            HERE.resolve().parent.parent / "tracker-page/scripts/tracker.py",
                            HOME / ".claude/skills/tracker-page/scripts/tracker.py") if p.exists()), None)
PROTECTED = {HOME, *(HOME / p for p in (
    "Library", "Library/Application Support", "Library/Caches", "Documents", "Desktop",
    "Downloads", "Pictures", "code", ".cache", ".local", ".local/share", ".config", ".ssh",
))}


def free_bytes():
    out = subprocess.check_output(["df", "-k", "/System/Volumes/Data"], text=True)
    return int(out.splitlines()[-1].split()[3]) * 1024


def track(run_dir, *args):
    if TRACKER and (run_dir / "status.json").exists():
        subprocess.run([sys.executable, str(TRACKER), args[0], str(run_dir), *args[1:]],
                       check=False, stdout=subprocess.DEVNULL)


def check_delete_target(raw):
    p = pathlib.Path(raw).expanduser()
    if p.is_symlink():
        raise SystemExit(f"refusing symlink: {p}")
    p = p.resolve()
    if p in PROTECTED:
        raise SystemExit(f"refusing top-level folder: {p}")
    if HOME not in p.parents:
        raise SystemExit(f"refusing path outside $HOME: {p}")
    return p


def delete(paths, log):
    code = 0
    for p in paths:
        if not p.exists():
            log.write(f"already absent: {p}\n")
            continue
        try:
            shutil.rmtree(p) if p.is_dir() else p.unlink()
        except OSError as e:
            log.write(f"error: {p}: {e}\n")
            code = 1
            continue
        log.write(f"{'deleted' if not p.exists() else 'STILL PRESENT'}: {p}\n")
        code = code or int(p.exists())
    return code


def main(argv):
    if len(argv) < 4 or argv[2] not in ("--", "--delete"):
        raise SystemExit(__doc__)
    run_dir, item, mode, rest = pathlib.Path(argv[0]), argv[1], argv[2], argv[3:]
    targets = [check_delete_target(a) for a in rest] if mode == "--delete" else None
    label = f"delete {[str(t) for t in targets]}" if targets else repr(rest)

    (run_dir / "reports").mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    report = run_dir / "reports" / f"{stamp}-{item}.txt"
    before = free_bytes()
    track(run_dir, "item", item, "--status", "in-progress", "--note", f"Running: {label}")
    track(run_dir, "log", f"Starting {item}: {label}; free {before / 2**30:.2f} GiB.")

    with report.open("w") as f:
        f.write(f"Command: {label}\nBefore free bytes: {before}\n\n")
        f.flush()
        if targets:
            code = delete(targets, f)
        else:
            env = {**os.environ, "HOMEBREW_NO_AUTO_UPDATE": "1"}
            try:
                code = subprocess.run(rest, stdout=f, stderr=subprocess.STDOUT, env=env,
                                      timeout=3600).returncode
            except subprocess.TimeoutExpired:
                code = 124
        after = free_bytes()
        f.write(f"\nExit code: {code}\nAfter free bytes: {after}\nChange: {after - before}\n")

    result = {"item": item, "command": label, "exit_code": code, "before_free": before,
              "after_free": after, "change": after - before, "report": str(report)}
    with (run_dir / "results.jsonl").open("a") as f:
        f.write(json.dumps(result) + "\n")
    note = (f"Exit {code}; free space {(after - before) / 2**30:+.2f} GiB, now {after / 2**30:.2f} GiB. "
            "A flat result usually means a local snapshot still holds the blocks.")
    track(run_dir, "item", item, "--status", "done" if code == 0 else "blocked", "--note", note,
          "--link", f"Report=reports/{report.name}")
    track(run_dir, "log", f"{item}: {note} Report: reports/{report.name}")
    print(json.dumps(result))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
