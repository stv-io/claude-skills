"""Tests for bin/pre-pr-review against throwaway git repos."""
import json
import os
import subprocess
from pathlib import Path

import pytest

BIN = Path(__file__).resolve().parent.parent / "bin" / "pre-pr-review"


def sh(cwd, *args):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, check=True).stdout


def run(cwd, *args):
    return subprocess.run([str(BIN), *args], cwd=cwd, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    sh(r, "git", "init", "-q", "-b", "main")
    (r / "keep.py").write_text("a\n")
    (r / "gone.py").write_text("x\n")
    (r / "old.txt").write_text("one two three four five six\n")
    sh(r, "git", "add", ".")
    sh(r, "git", "commit", "-qm", "base")
    sh(r, "git", "switch", "-qc", "feat")
    (r / "keep.py").write_text("a\nb\n")
    (r / "gone.py").unlink()
    sh(r, "git", "mv", "old.txt", "new.txt")
    (r / "added.py").write_text("y\n")
    sh(r, "git", "add", "-A")
    sh(r, "git", "commit", "-qm", "feat")
    (r / "untracked.md").write_text("u\n")
    return r


def test_info_lists_changes(repo):
    p = run(repo, "info", "main")
    assert p.returncode == 0, p.stderr
    i = json.loads(p.stdout)
    paths = {c["path"]: c["status"] for c in i["changed"]}
    assert paths == {"keep.py": "modified", "added.py": "added", "new.txt": "renamed",
                     "untracked.md": "untracked"}
    assert sorted(i["deleted"]) == ["gone.py", "old.txt"]
    assert i["uncommitted"] is True
    assert i["description"].endswith(os.path.join(".git", "pre-pr-review", "description.md"))


def test_crit_args_description_first_no_deleted(repo):
    lines = run(repo, "crit-args", "main").stdout.splitlines()
    assert lines[0].endswith("description.md")
    assert "gone.py" not in lines and "old.txt" not in lines
    assert set(lines[1:]) == {"keep.py", "added.py", "new.txt", "untracked.md"}


def test_init_copies_single_template(repo):
    (repo / ".github").mkdir()
    (repo / ".github" / "pull_request_template.md").write_text("## Why\n")
    p = run(repo, "init", "main")
    assert p.returncode == 0, p.stderr
    desc = repo / ".git" / "pre-pr-review" / "description.md"
    assert desc.read_text() == "## Why\n"
    assert (repo / ".git" / "pre-pr-review" / "assets").is_dir()
    desc.write_text("edited\n")
    run(repo, "init", "main")
    assert desc.read_text() == "edited\n", "init must not overwrite an existing draft"


def test_runs_from_a_subfolder(repo):
    (repo / "sub").mkdir()
    lines = run(repo / "sub", "crit-args", "main").stdout.splitlines()
    assert "keep.py" in lines


def test_bad_base_exits_2(repo):
    assert run(repo, "info", "nosuchbase").returncode == 2


def test_unknown_command_exits_2(repo):
    assert run(repo, "frobnicate").returncode == 2
