"""tracker.py without a browser: helpers, rendering, the feedback file and its CLI."""
import json, re, shutil, subprocess

import pytest

import tracker
from conftest import SCRIPTS, cli, comments


def page(d): return (d / 'index.html').read_text()


@pytest.mark.parametrize('link, want', [
    ('notes/a.md', '/md?p=notes/a.md'),
    ('../docs/x.md#part', '/md?p=../docs/x.md#part'),
    ('report.pdf', 'report.pdf'),
    ('https://h/x.md', 'https://h/x.md'),
    ('/abs/x.md', '/abs/x.md'),
    ('#anchor', '#anchor'),
])
def test_mdlink(link, want):
    assert tracker.mdlink(link) == want


def test_linkify_links_urls_and_existing_files_only(tmp_path):
    (tmp_path / 'r.md').write_text('x')
    out = tracker.linkify('see r.md, missing.md and https://e.com/a?b=1&c=2 <script>', str(tmp_path))
    assert '<a href="/md?p=r.md">r.md</a>' in out
    assert 'missing.md' in out and 'href="/md?p=missing.md"' not in out
    assert '<a href="https://e.com/a?b=1&amp;c=2">' in out
    assert '&lt;script&gt;' in out and '<script>' not in out


def test_short_time():
    today = tracker.now()
    assert tracker.short(today) == today[11:] and today.endswith('UTC')
    assert tracker.short('2020-01-02 03:04 UTC') == '2020-01-02 03:04 UTC'


def test_render_counts_title_and_filters(board):
    html = page(board)
    assert '<title>(3) Demo &lt;b&gt;tracker&lt;/b&gt;</title>' in html  # review + decision + blocked, escaped
    assert '1 done (17%)' in html
    rows = dict(re.findall(r'data-item="(\d+)" data-f="([^"]*)"', html))
    assert rows == {'1': 'done', '2': 'open', '3': 'open needs', '4': 'open needs', '5': 'open needs', '6': 'open'}
    assert html.count('<details class="box" open>') == 3  # no phase is finished yet


def test_finished_phase_is_folded(board):
    cli('item', board, 2, '--status', 'done')
    html = page(board)
    p0 = html.split('<details class="box"')[1]
    assert p0.startswith('>') and 'P0' in p0  # no " open" attribute


def test_items_without_phase_and_interleaved_phases(tmp_path):
    d = tmp_path / 't'; cli('init', d, '--title', 'T')
    cli('item', d, 'a', '--phase', 'X'); cli('item', d, 'b'); cli('item', d, 'c', '--phase', 'X')
    html = page(d)
    assert html.count('<details class="box"') == 1 and '<section class="box">' in html
    assert re.search(r'X <span class="mute">0 of 2</span>', html)  # a and c grouped together


def test_single_and_multiple_flash_entries(board):
    assert '<b>Blocked</b><span>Token expired</span>' in page(board)
    cli('block', board, 'Second thing')
    assert '<b>Blocked</b><ul><li>Token expired</li><li>Second thing</li></ul>' in page(board)
    cli('block', board, '--clear')
    assert 'class="flash bad"' not in page(board)


def test_log_is_utc_and_shown_newest_first(board):
    cli('log', board, 'Second')
    lines = (board / 'LOG.md').read_text().splitlines()
    assert re.match(r'- \d{4}-\d\d-\d\d \d\d:\d\d UTC Second$', lines[-1])
    html = page(board)
    assert html.index('Second') < html.index('Started')


def test_rev_changes_only_when_content_changes(board):
    rev = lambda: re.search(r'name="tracker-rev" content="(\w+)"', page(board)).group(1)
    a = rev(); cli('render', board); assert rev() == a
    cli('log', board, 'news'); assert rev() != a


def test_add_comment_validates(board):
    with pytest.raises(ValueError): tracker.add_comment(str(board), '1', '   ')
    with pytest.raises(ValueError): tracker.add_comment(str(board), '99', 'no such item')
    with pytest.raises(ValueError): tracker.add_comment(str(board), None, 'x' * 10001)
    assert tracker.add_comment(str(board), 1, 'int id works') == 1
    assert tracker.add_comment(str(board), None, 'general') == 2
    assert [(c['item'], c['state']) for c in comments(board)] == [('1', 'open'), (None, 'open')]


def test_feedback_cli_lists_and_resolves(board):
    tracker.add_comment(str(board), '4', 'Go with A'); tracker.add_comment(str(board), None, 'General <i>note</i>')
    tracker.render(str(board))
    html = page(board)
    assert 'Go with A' in html and 'General &lt;i&gt;note&lt;/i&gt;' in html
    assert 'data-f="open needs feedback"' in html and 'Comments <span class="count">2</span>' in html
    out = cli('feedback', board).stdout
    assert '#1 [saved, not sent yet] item 4' in out and '#2 [saved, not sent yet] general' in out
    cli('feedback', board, '--resolve', 1, '--reply', 'Done, see reports/r.md')
    assert '#1' not in cli('feedback', board).stdout
    assert '#1 [resolved]' in cli('feedback', board, '--all').stdout
    assert comments(board)[0]['reply'] == 'Done, see reports/r.md'
    assert '↳ Done, see <a href="/md?p=reports/r.md">' in page(board)
    assert cli('feedback', board, '--resolve', 9, check=False).returncode != 0


def test_status_is_validated(board):
    r = cli('item', board, 1, '--status', 'nope', check=False)
    assert r.returncode != 0 and 'status must be one of' in r.stderr


def test_no_partial_temp_files_left(board):
    assert not list(board.glob('.*.tmp'))


@pytest.mark.skipif(not shutil.which('/usr/bin/python3'), reason='no system python')
def test_scripts_compile_on_system_python():
    """macOS ships Python 3.9; keep the scripts free of 3.12-only syntax (nested f-string quotes)."""
    for f in ('tracker.py', 'review.py'):
        subprocess.run(['/usr/bin/python3', '-m', 'py_compile', str(SCRIPTS / f)], check=True)


def test_send_then_wait_hands_over_each_comment_once(board):
    d = str(board)
    tracker.add_comment(d, '1', 'first'); tracker.add_comment(d, None, 'second')
    assert tracker.take_sent(d) == []  # saved but not sent: nothing for the agent yet
    assert tracker.send_comments(d) == 2 and tracker.send_comments(d) == 0
    got = tracker.wait_sent(d, timeout=1, every=0.05)
    assert [c['text'] for c in got] == ['first', 'second']
    assert tracker.wait_sent(d, timeout=0.2, every=0.05) == []  # already delivered
    assert 'seen by Claude' in page(board)
    tracker.add_comment(d, '2', 'third')
    tracker.render(d, quiet=True); assert 'Send 1 comment to Claude' in page(board)


def test_wait_cli_blocks_until_sent(board):
    import subprocess, sys, time
    tracker.add_comment(str(board), '3', 'please look')
    proc = subprocess.Popen([sys.executable, str(SCRIPTS / 'tracker.py'), 'feedback', str(board), '--wait', '--timeout', '20'], stdout=subprocess.PIPE, text=True)
    time.sleep(1); assert proc.poll() is None  # still waiting: nothing sent yet
    tracker.send_comments(str(board))
    out, _ = proc.communicate(timeout=15)
    assert proc.returncode == 0 and '#1 [seen by Claude] item 3' in out and '--resolve ID' in out
    r = cli('feedback', board, '--wait', '--timeout', '0.5', check=False)
    assert r.returncode == 3 and 'nothing sent' in r.stdout


def test_send_button_only_when_something_is_unsent(board):
    assert 'id="send"' not in page(board)
    tracker.add_comment(str(board), '1', 'x'); tracker.render(str(board), quiet=True)
    assert 'Send 1 comment to Claude' in page(board)
    tracker.send_comments(str(board)); tracker.render(str(board), quiet=True)
    assert 'id="send"' not in page(board) and 'sent to Claude' in page(board)
