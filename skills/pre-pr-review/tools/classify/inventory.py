"""List git repos under a folder (default ~/code) with their origin URL, as JSON.

Reads .git/config directly; runs no git commands and writes nothing.
Usage: inventory.py [ROOT] > repos.json
"""
import json, os, re, sys

root = os.path.abspath(os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else "~/code"))
out = []
for dirpath, dirnames, filenames in os.walk(root):
    depth = dirpath[len(root):].count(os.sep)
    dirnames[:] = [d for d in dirnames if d not in ("node_modules", ".terraform", ".terragrunt-cache", "worktrees", "vendor", ".venv")]
    if ".git" in dirnames or ".git" in filenames:
        gitpath = os.path.join(dirpath, ".git")
        cfg = None
        if os.path.isdir(gitpath):
            cfg = os.path.join(gitpath, "config")
        else:  # worktree/submodule pointer
            try:
                with open(gitpath) as f:
                    m = re.match(r"gitdir:\s*(.*)", f.read().strip())
                gd = os.path.normpath(os.path.join(dirpath, m.group(1)))
                common = os.path.join(gd, "commondir")
                if os.path.exists(common):
                    gd = os.path.normpath(os.path.join(gd, open(common).read().strip()))
                cfg = os.path.join(gd, "config")
            except Exception:
                pass
        url = ""
        if cfg and os.path.exists(cfg):
            txt = open(cfg).read()
            m = re.search(r'\[remote "origin"\][^\[]*?url\s*=\s*(\S+)', txt)
            url = m.group(1) if m else ""
        out.append({"path": dirpath.replace(os.path.expanduser("~"), "~"), "origin": url})
        dirnames[:] = []  # don't descend into repos
    if depth >= 4:
        dirnames[:] = []

json.dump(out, sys.stdout, indent=1)
