"""docs-sweep against throwaway git repos: each test builds a base, makes a change, runs the script."""
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "bin" / "docs-sweep"


def sh(repo, *args):
    subprocess.run(args, cwd=repo, check=True, capture_output=True, text=True)


def sweep(repo, *args):
    r = subprocess.run([sys.executable, "-I", str(SCRIPT), *args], cwd=repo,
                       capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


@pytest.fixture
def repo(tmp_path):
    """A repo whose README mentions an instance type, a port, a SQL name and a script path."""
    sh(tmp_path, "git", "init", "-q", "-b", "main")
    sh(tmp_path, "git", "config", "user.email", "t@example.com")
    sh(tmp_path, "git", "config", "user.name", "t")
    (tmp_path / "main.tf").write_text('instance_type = "t3.medium"\nport = 8080\n')
    (tmp_path / "schema.sql").write_text("-- owner: old_sql_owner\nselect 1;\n")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "old-deploy.sh").write_text("echo hi\n")
    (tmp_path / "README.md").write_text(
        "# Readme\n\n## Setup\n\nUse t3.medium on port 8080, owner old_sql_owner.\n"
        "Run `scripts/old-deploy.sh`. Logs go to `LOG.md`.\n")
    sh(tmp_path, "git", "add", "-A")
    sh(tmp_path, "git", "commit", "-qm", "base")
    sh(tmp_path, "git", "branch", "base")
    sh(tmp_path, "git", "switch", "-qc", "feat")
    return tmp_path


def edit(path, old, new):
    path.write_text(path.read_text().replace(old, new))


def test_committed_change_is_found(repo):
    edit(repo / "main.tf", "t3.medium", "t3.large")
    sh(repo, "git", "commit", "-qam", "bigger")
    code, out, _ = sweep(repo, "terms", "base")
    assert code == 1
    assert "t3.medium" in out and "README.md:5" in out


def test_uncommitted_change_is_found(repo):
    edit(repo / "main.tf", "t3.medium", "t3.large")  # not committed, not staged
    code, out, _ = sweep(repo, "terms", "base")
    assert code == 1 and "t3.medium" in out


def test_bare_numbers_are_not_terms(repo):
    edit(repo / "main.tf", "8080", "9090")
    code, out, _ = sweep(repo, "terms", "base")
    assert code == 0 and "8080" not in out


def test_removed_line_starting_with_dashes_is_read(repo):
    edit(repo / "schema.sql", "-- owner: old_sql_owner\n", "")
    sh(repo, "git", "commit", "-qam", "drop comment")
    _, out, _ = sweep(repo, "terms", "base")
    assert "old_sql_owner" in out


def test_renamed_file_is_a_term(repo):
    sh(repo, "git", "mv", "scripts/old-deploy.sh", "scripts/deploy.sh")
    sh(repo, "git", "commit", "-qm", "rename")
    _, out, _ = sweep(repo, "terms", "base")
    assert "scripts/old-deploy.sh   (removed" in out


def test_moved_value_is_not_reported(repo):
    edit(repo / "main.tf", 'instance_type = "t3.medium"\n', "")
    (repo / "vars.tf").write_text('default = "t3.medium"\n')
    sh(repo, "git", "add", "-A")
    sh(repo, "git", "commit", "-qm", "move")
    code, out, _ = sweep(repo, "terms", "base")
    assert code == 0 and "t3.medium" not in out


def test_bad_base_fails_loudly(repo):
    code, out, err = sweep(repo, "terms", "no-such-ref")
    assert code == 2 and "docs-sweep" in err


def test_unknown_command_exits_2(repo):
    assert sweep(repo, "nope")[0] == 2


def test_not_a_repo(tmp_path):
    assert sweep(tmp_path, "paths")[0] == 2


def test_paths_reports_missing_path_but_not_bare_names(repo):
    code, out, _ = sweep(repo, "paths")
    assert code == 0                                 # `LOG.md` is a bare name: an example, not a path
    sh(repo, "git", "rm", "-q", "scripts/old-deploy.sh")
    code, out, _ = sweep(repo, "paths")
    assert code == 1 and "`scripts/old-deploy.sh` does not exist" in out


def test_untracked_markdown_is_checked(repo):
    (repo / "NEW.md").write_text("[setup](README.md#setup) [gone](nope.md) `scripts/gone.sh`\n")
    code, out, _ = sweep(repo, "links")
    assert code == 1 and "NEW.md:1: link to nope.md" in out and "#setup" not in out
    _, out, _ = sweep(repo, "paths")
    assert "NEW.md:1: `scripts/gone.sh`" in out


def test_ignored_files_are_not_checked(repo):
    (repo / ".gitignore").write_text("build/\n")
    (repo / "build").mkdir()
    (repo / "build" / "out.md").write_text("[gone](nope.md)\n")
    code, out, _ = sweep(repo, "links")
    assert code == 0, out


@pytest.mark.parametrize("heading, anchor", [
    ("Setup & Install", "setup--install"),
    ("snake_case heading", "snake_case-heading"),
    ("FAQ", "faq-1"),                                # the second FAQ
])
def test_anchors(repo, heading, anchor):
    (repo / "doc.md").write_text(f"## FAQ\n\n## {heading}\n\n[x](#{anchor}) [y](#missing)\n")
    _, out, _ = sweep(repo, "links")
    assert f"#{anchor}:" not in out and "no heading #missing" in out
