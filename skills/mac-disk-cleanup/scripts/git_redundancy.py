#!/usr/bin/env python3
"""Evidence for git cleanups. Read-only.

    git_redundancy.py clone <candidate> <keeper>   # is the candidate clone safe to delete?
    git_redundancy.py unreachable <repo>           # what would `git gc --prune=now` drop?

`clone` passes only when the candidate has no changes, no stashes, no extra
worktrees, no other process inside it, and every branch, tag, HEAD and reflog
commit already exists in the keeper.
"""
import os
import subprocess
import sys
from collections import Counter

ENV = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], env=ENV, capture_output=True, text=True)


def clone(cand, keeper):
    problems = []
    if git(cand, "status", "--porcelain").stdout.strip():
        problems.append("uncommitted or untracked changes")
    ignored = git(cand, "ls-files", "--others", "--ignored", "--exclude-standard", "--directory").stdout.split("\n")
    ignored = [i for i in ignored if i]
    if git(cand, "stash", "list").stdout.strip():
        problems.append("has stashes")
    if len(git(cand, "worktree", "list").stdout.splitlines()) > 1:
        problems.append("has linked worktrees (use git worktree remove)")
    commits = set(git(cand, "for-each-ref", "--format=%(objectname)", "refs/heads", "refs/tags").stdout.split())
    commits |= set(git(cand, "reflog", "--format=%H").stdout.split())
    commits.add(git(cand, "rev-parse", "HEAD").stdout.strip())
    missing = [c for c in commits if c and git(keeper, "cat-file", "-e", f"{c}^{{commit}}").returncode]
    if missing:
        problems.append(f"{len(missing)} commits not in keeper, e.g. {missing[:3]}")
    lsof = subprocess.run(["lsof", "+D", cand], capture_output=True, text=True).stdout.splitlines()[1:]
    others = [l for l in lsof if str(os.getpid()) not in l and "lsof" not in l]
    if others:
        problems.append(f"{len(others)} open files/processes inside, e.g. {others[0][:120]}")
    print(f"candidate: {cand}\nkeeper:    {keeper}\ncommits checked: {len(commits)}")
    if ignored:
        print(f"ignored files present (not in git, lost on delete): {ignored[:10]}")
    print("VERDICT:", "SAFE TO DELETE" if not problems else "KEEP\n  - " + "\n  - ".join(problems))
    return 1 if problems else 0


def unreachable(repo):
    print(git(repo, "count-objects", "-vH").stdout)
    print("reachable from refs + reflogs:",
          git(repo, "rev-list", "--all", "--reflog", "--objects", "--disk-usage=human").stdout.strip())
    fsck = git(repo, "fsck", "--unreachable", "--no-progress").stdout.split("\n")
    kinds = Counter(l.split()[1] for l in fsck if l.startswith("unreachable"))
    print("unreachable objects:", dict(kinds))
    subjects = Counter()
    for l in fsck:
        if l.startswith("unreachable commit"):
            subjects[git(repo, "log", "-1", "--format=%ad %s", "--date=short", l.split()[2]).stdout.strip()] += 1
    for s, n in subjects.most_common(10):
        print(f"  {n:4d}  {s}")
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) == 3 and a[0] == "clone":
        sys.exit(clone(*a[1:]))
    if len(a) == 2 and a[0] == "unreachable":
        sys.exit(unreachable(a[1]))
    raise SystemExit(__doc__)
