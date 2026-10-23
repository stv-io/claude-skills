#!/usr/bin/env python3
"""Find and remove Terraform/OpenTofu provider binaries copied into projects.

    provider_binaries.py scan <root> <out.json>     # read-only
    provider_binaries.py delete <candidates.json>   # re-checks every file first

Only files named terraform-provider-* or tofu-provider-* inside a .terraform
or .terragrunt-cache folder are touched. State, lock files and backend config
stay, so the next `init` downloads the same versions again.
"""
import json
import os
import pathlib
import subprocess
import sys

PREFIXES = ("terraform-provider-", "tofu-provider-")
CACHE_DIRS = (".terraform", ".terragrunt-cache")


def in_scope(path, cache_root):
    p = pathlib.Path(path)
    return (p.name.startswith(PREFIXES) and pathlib.Path(cache_root).name in CACHE_DIRS
            and path.startswith(cache_root + "/"))


def scan(root, out):
    files, seen = [], set()
    for dirpath, dirnames, filenames in os.walk(root):
        # find the outermost cache root above this directory, if any
        parts = pathlib.Path(dirpath).parts
        idx = next((i for i, part in enumerate(parts) if part in CACHE_DIRS), None)
        if idx is None:
            dirnames[:] = [d for d in dirnames if d not in ("node_modules", ".git")]
            continue
        cache_root = str(pathlib.Path(*parts[:idx + 1]))
        for name in filenames:
            p = os.path.join(dirpath, name)
            if not name.startswith(PREFIXES) or os.path.islink(p) or not os.path.isfile(p):
                continue
            st = os.stat(p)
            key = (st.st_dev, st.st_ino)
            files.append({"path": p, "cache_root": cache_root,
                          "allocated_bytes": st.st_blocks * 512, "counted_once": key not in seen})
            seen.add(key)
    total = sum(f["allocated_bytes"] for f in files if f["counted_once"])
    json.dump({"root": root, "files": files}, open(out, "w"), indent=1)
    print(f"{len(files)} provider binaries, {total / 2**30:.2f} GiB allocated -> {out}")


def delete(candidates):
    busy = subprocess.run(["pgrep", "-fl", r"(^|/)(terraform|terragrunt|tofu)( |$)"],
                          capture_output=True, text=True).stdout
    busy = [l for l in busy.splitlines() if "mcp" not in l]
    if busy:
        raise SystemExit("terraform/terragrunt/tofu running, stop first:\n" + "\n".join(busy))
    counts, freed = {}, 0
    for f in json.load(open(candidates))["files"]:
        p = pathlib.Path(f["path"])
        if not in_scope(f["path"], f["cache_root"]):
            result = "skipped: scope"
        elif not p.exists():
            result = "already absent"
        elif p.is_symlink() or not p.is_file():
            result = "skipped: not a regular file"
        else:
            p.unlink()
            result = "deleted"
            freed += f["allocated_bytes"] if f["counted_once"] else 0
        counts[result] = counts.get(result, 0) + 1
        if result.startswith("skipped"):
            print(result, p)
    print(counts, f"{freed / 2**30:.2f} GiB allocated removed")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "scan":
        scan(os.path.abspath(os.path.expanduser(sys.argv[2])), sys.argv[3])
    elif len(sys.argv) == 3 and sys.argv[1] == "delete":
        delete(sys.argv[2])
    else:
        raise SystemExit(__doc__)
