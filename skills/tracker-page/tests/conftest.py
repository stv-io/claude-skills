import http.server, json, pathlib, subprocess, sys, threading

import pytest

SCRIPTS = pathlib.Path(__file__).resolve().parent.parent / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import tracker  # noqa: E402


def cli(*args, check=True):
    """Run tracker.py the way the skill does, as a separate process."""
    return subprocess.run([sys.executable, str(SCRIPTS / 'tracker.py'), *map(str, args)], capture_output=True, text=True, check=check)


@pytest.fixture
def board(tmp_path):
    """A tracker with every status, two phases, a blocker, a decision, a log and a linked report."""
    d = tmp_path / 'trk'
    cli('init', d, '--title', 'Demo <b>tracker</b>', '--subtitle', 'Source list: reports/r.md')
    (d / 'reports').mkdir(); (d / 'reports' / 'r.md').write_text('# r\n')
    for i, (phase, st) in enumerate([('P0', 'done'), ('P0', 'in-progress'), ('P1', 'review'), ('P1', 'decision'), ('P1', 'blocked'), ('P2', 'todo')], 1):
        cli('item', d, i, '--phase', phase, '--title', f'Item {i}', '--status', st)
    cli('item', d, 2, '--note', 'see reports/r.md and https://example.com/a?b=1&c=2')
    cli('block', d, 'Token expired'); cli('ask', d, 'Pick A or B?'); cli('log', d, 'Started')
    return d


@pytest.fixture
def server(board):
    """tracker.py's own handler on a free port, without mdserve."""
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), tracker.handler(str(board), None))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f'http://127.0.0.1:{srv.server_address[1]}', board
    srv.shutdown(); srv.server_close()


def comments(d): return json.loads((d / 'feedback.json').read_text())['comments'] if (d / 'feedback.json').exists() else []
