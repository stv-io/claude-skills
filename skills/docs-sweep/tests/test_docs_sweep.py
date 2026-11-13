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


# --- claims -------------------------------------------------------------------------------------

def write(repo, files):
    for name, text in files.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(text)


def test_count_of_folders(repo):
    write(repo, {f"modules/m{i}/main.tf": "" for i in range(3)})
    write(repo, {"docs/a.md": "We have three modules.\n",
                 "docs/b.md": "Seven Terraform modules live here.\n",
                 "docs/c.md": "One of the modules is new. Two new modules landed.\n",
                 "CHANGELOG.md": "Added two modules.\n"})
    code, out, _ = sweep(repo, "claims")
    assert "docs/b.md:1: says Seven modules; modules/ has 3" in out
    assert "a.md" not in out and "c.md" not in out and "CHANGELOG" not in out
    assert code == 1


PINS = {
    "versions.tf": 'terraform {\n  required_version = ">= 1.9.0"\n}\n',
    "eks.tf": 'module "eks" {\n  source  = "terraform-aws-modules/eks/aws"\n  version = "~> 20.8"\n}\n',
    "argocd/app.yaml": "spec:\n  source:\n    chart: generic-deployment\n    targetRevision: 0.6.0\n",
    "chart/Chart.yaml": "dependencies:\n  - name: redis\n    version: 19.0.1\n"
                        "    repository: https://charts.bitnami.com/bitnami\n",
    ".github/workflows/ci.yml": "jobs:\n  t:\n    steps:\n      - uses: actions/checkout@v4\n",
    "deploy.yaml": "containers:\n  - image: ghcr.io/acme/api:1.4.2\n",
    ".tool-versions": "helm 3.15.2\n",
}


@pytest.mark.parametrize("prose, stale", [
    ("Requires Terraform 1.9 or later.", False),
    ("Requires Terraform 1.8.", True),
    ("The eks module is on 20.x.", False),
    ("The eks module is on 19.21.", True),
    ("generic-deployment 0.6.0 is live.", False),
    ("generic-deployment v0.5.3 is live.", True),
    ("redis 19.0.1, bitnami.", False),
    ("redis 18.2 is used.", True),
    ("We use checkout v3.", True),
    ("We use checkout v4.", False),
    ("api 1.4.2 is deployed.", False),
    ("api:1.3.0 is deployed.", True),
    ("Install helm 3.15.", False),
    ("Install helm 3.14.", True),
])
def test_versions_in_prose(repo, prose, stale):
    write(repo, {**PINS, "README.md": prose + "\n"})
    _, out, _ = sweep(repo, "claims")
    assert ("README.md:1:" in out) == stale, out


def test_name_followed_by_extension_is_not_a_claim(repo):
    write(repo, {"root.hcl": 'terragrunt_version_constraint = "= 1.1.5"\n',
                 "README.md": "Resolved version from terragrunt.hcl : >= 1.8.0\n"})
    code, out, _ = sweep(repo, "claims")
    assert code == 0, out


def test_module_readme_answers_to_its_own_pins(repo):
    write(repo, {"a/versions.tf": 'terraform {\n  required_version = ">= 1.5"\n}\n',
                 "b/versions.tf": 'terraform {\n  required_version = ">= 1.11"\n}\n',
                 "b/README.md": "| terraform | >= 1.5 |\n"})
    _, out, _ = sweep(repo, "claims")
    assert "b/README.md:1: says terraform 1.5; pinned 1.11 (b/versions.tf:2)" in out
