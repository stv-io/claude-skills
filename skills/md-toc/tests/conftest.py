import importlib.machinery
import importlib.util
import re
import shutil
import subprocess
import sys
from html import unescape
from urllib.parse import unquote
from pathlib import Path

import pytest

HERE = Path(__file__).parent
SCRIPT = HERE.parent / "bin" / "md-toc"
FIXTURES = HERE / "fixtures"

# bin/md-toc has no .py suffix, so load it by path
_loader = importlib.machinery.SourceFileLoader("mdtoc", str(SCRIPT))
_spec = importlib.util.spec_from_loader("mdtoc", _loader)
mdtoc = importlib.util.module_from_spec(_spec)
_loader.exec_module(mdtoc)


def run(path, *args):
    """Run the CLI; return (exit code, stdout, stderr)."""
    p = subprocess.run([sys.executable, str(SCRIPT), str(path), *args],
                       capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def broken_links(html):
    """#targets that an <a href="#x"> points at but no element has id="x".
    Renderers percent-encode non-ASCII in hrefs; browsers decode before matching."""
    ids = {unescape(x) for x in re.findall(r'\bid="([^"]+)"', html)}
    hrefs = [unquote(unescape(x)) for x in re.findall(r'href="#([^"]+)"', html)]
    return hrefs, [h for h in hrefs if h not in ids]


@pytest.fixture
def doc(tmp_path):
    """Copy a fixture into tmp_path and return its path."""
    def make(name):
        dst = tmp_path / name
        shutil.copy(FIXTURES / name, dst)
        return dst
    return make
