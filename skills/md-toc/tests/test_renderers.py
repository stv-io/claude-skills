"""Click-through proof in real renderers: every href="#x" in the rendered HTML
must have an element with id="x". Each test skips when its renderer is missing;
CI provides all three."""
import json
import os
import shutil
import socket
import subprocess
import time
import urllib.request

import pytest

from conftest import broken_links, run

# CI sets this so a missing renderer fails instead of skipping quietly.
STRICT = os.environ.get("MD_TOC_REQUIRE_RENDERERS") == "1"


def need(ok, reason):
    if not ok:
        (pytest.fail if STRICT else pytest.skip)(reason)


@pytest.fixture(params=["runbook.md", "tricky.md"])
def generated(request, doc):
    p = doc(request.param)
    code, out, err = run(p)
    assert code == 0, out + err
    return p


def test_python_markdown_without_heading_ids(generated):
    """Python-Markdown with no toc extension makes no heading ids, like mdserve."""
    need(_has("markdown"), "Python-Markdown not installed")
    import markdown
    html = markdown.markdown(generated.read_text(), extensions=["fenced_code"])
    hrefs, missing = broken_links(html)
    assert hrefs and not missing


def test_without_anchors_such_viewers_break(doc):
    """The control: proves the test above would catch the original bug."""
    need(_has("markdown"), "Python-Markdown not installed")
    import markdown
    p = doc("runbook.md")
    run(p, "--no-anchors")
    _, missing = broken_links(markdown.markdown(p.read_text()))
    assert missing


def _has(module):
    import importlib.util
    return importlib.util.find_spec(module) is not None


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_mdserve(generated):
    need(shutil.which("mdserve"), "mdserve not installed")
    port = _free_port()
    proc = subprocess.Popen(["mdserve", str(generated), "-p", str(port)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        html = None
        for _ in range(50):
            try:
                html = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1).read().decode()
                break
            except OSError:
                time.sleep(0.1)
        assert html, "mdserve did not start"
    finally:
        proc.terminate()
        proc.wait()
    hrefs, missing = broken_links(html)
    assert hrefs and not missing


def _gh_ok():
    return shutil.which("gh") and subprocess.run(
        ["gh", "auth", "status"], capture_output=True).returncode == 0


def test_github_renderer(generated):
    """Same check against GitHub's own HTML. Fixtures only: nothing private is sent."""
    need(_gh_ok(), "gh not logged in")
    body = json.dumps({"text": generated.read_text(), "mode": "markdown"})
    html = subprocess.run(["gh", "api", "-X", "POST", "/markdown", "--input", "-"],
                          input=body, capture_output=True, text=True, check=True).stdout
    # GitHub prefixes ids with user-content- and its page script maps #x to them
    html = html.replace('id="user-content-', 'id="')
    hrefs, missing = broken_links(html)
    assert hrefs and not missing
    code, out, _ = run(generated, "--github")
    assert code == 0, out
