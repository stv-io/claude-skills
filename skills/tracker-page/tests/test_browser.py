"""The pages' JavaScript in a real (headless) Chromium: filters, comments, review keys, summary, accessibility basics.

Needs Playwright and its Chromium: `uv run --with pytest --with playwright playwright install chromium` once.
"""
import json, re, shutil

import pytest

pw = pytest.importorskip('playwright.sync_api')

import review, tracker
from conftest import comments


@pytest.fixture(scope='module')
def browser():
    with pw.sync_playwright() as p:
        try: b = p.chromium.launch()
        except Exception as e: pytest.skip(f'no Chromium for Playwright: {e}')
        yield b; b.close()


@pytest.fixture(params=['light', 'dark'])
def page(browser, request):
    ctx = browser.new_context(color_scheme=request.param, permissions=['clipboard-read', 'clipboard-write'])
    pg = ctx.new_page(); errors = []; pg.on('pageerror', lambda e: errors.append(str(e)))
    yield pg
    ctx.close()
    assert errors == []


def visible_items(pg): return [r.get_attribute('data-item') for r in pg.locator('.row:visible').all()]


def test_filter_tabs(page, server):
    url, _ = server
    page.goto(url + '/')
    assert visible_items(page) == ['1', '2', '3', '4', '5', '6']
    page.click('.tabs a[href="#needs"]')
    assert visible_items(page) == ['3', '4', '5']
    assert page.get_attribute('.tabs a[href="#needs"]', 'aria-current') == 'true'
    page.click('.tabs a[href="#done"]')
    assert visible_items(page) == ['1']
    page.reload()  # the filter survives a reload through the URL hash
    assert visible_items(page) == ['1']


def test_comment_is_saved_through_the_server(page, server):
    url, d = server
    page.goto(url + '/')
    page.click('#i4 [data-comment]')
    page.fill('#i4 .compose textarea', 'Go with B')
    with page.expect_navigation(): page.click('#i4 .compose .primary')
    assert comments(d)[0]['item'] == '4'
    assert page.locator('#i4 .cmt').inner_text().endswith('Go with B')
    assert 'Comments 1' in page.locator('.tabs').inner_text().replace('\n', ' ')


def test_general_comment_and_escape_closes(page, server):
    url, d = server
    page.goto(url + '/')
    page.click('#gen [data-comment]'); page.keyboard.press('Escape')
    assert page.locator('.compose').count() == 0
    page.click('#gen [data-comment]'); page.fill('#gen textarea', 'Hello')
    with page.expect_navigation(): page.keyboard.press('Meta+Enter')
    assert comments(d)[0]['item'] is None


def test_comment_offline_falls_back_to_clipboard(page, board):
    page.goto((board / 'index.html').as_uri())
    page.click('#i2 [data-comment]'); page.fill('#i2 textarea', 'From a file')
    page.click('#i2 .compose .primary')
    page.wait_for_function("document.querySelector('#i2 .msg').textContent.length > 0")
    assert 'opened as a file' in page.inner_text('#i2 .msg') and 'Copied to the clipboard' in page.inner_text('#i2 .msg')
    assert comments(board) == []


def test_page_reloads_when_content_changes(page, server):
    url, d = server
    page.clock.install()
    page.goto(url + '/')
    tracker.add_comment(str(d), '1', 'changed behind the page'); tracker.render(str(d))
    with page.expect_navigation(): page.clock.run_for(16000)
    assert 'changed behind the page' in page.content()


def test_review_keys_and_summary(page, tmp_path):
    cards = tmp_path / 'cards.json'
    cards.write_text(json.dumps({'title': 'R', 'groups': [{'name': 'G', 'cards': [
        {'id': 'A', 'before': 'one', 'after': 'two'}, {'id': 'B', 'before': 'x', 'after': 'y z'}, {'id': 'C', 'before': 's', 'after': 's'}]}]}))
    review.build(cards, tmp_path / 'out')
    page.goto((tmp_path / 'out' / 'g.html').as_uri())
    page.keyboard.press('j'); page.keyboard.press('a')
    page.keyboard.press('j'); page.keyboard.press('h'); page.keyboard.press('n'); page.keyboard.type('fix wording\nplease')
    assert page.inner_text('#done') == '2 of 3 reviewed'
    page.click('#allunch')
    page.click('#copy')
    assert page.inner_text('#sum') == 'G / A: approve\nG / B: hold — fix wording please\nG / C: approve'
    page.reload()  # choices are kept in the browser between visits
    assert page.inner_text('#done') == '3 of 3 reviewed'
    assert page.is_checked('#g-b input[value=hold]')


def test_accessible_names(page, server):
    """Cheap a11y checks: every button and textarea has a name, the status icons are labelled."""
    url, _ = server
    page.goto(url + '/')
    page.click('#i3 [data-comment]')
    assert page.get_attribute('#i3 textarea', 'aria-label') == 'Comment on item 3'
    for lab in page.locator('svg.ico').all():
        assert lab.get_attribute('aria-label')
    for b in page.locator('button').all():
        assert b.inner_text().strip()


def test_old_server_gets_a_restart_hint(page, board):
    """A tracker re-rendered by the new script but served by an old `serve` (no POST support) answers 501."""
    import http.server, threading
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), lambda *a, **k: http.server.SimpleHTTPRequestHandler(*a, directory=str(board), **k))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        page.goto(f'http://127.0.0.1:{srv.server_address[1]}/')
        page.click('#i1 [data-comment]'); page.fill('#i1 textarea', 'hi'); page.click('#i1 .compose .primary')
        page.wait_for_function("document.querySelector('#i1 .msg').textContent.length > 0")
        assert 'older tracker.py. Restart tracker.py serve' in page.inner_text('#i1 .msg')
    finally:
        srv.shutdown(); srv.server_close()


def test_send_to_claude_button(page, server):
    url, d = server
    tracker.add_comment(str(d), '4', 'Go with B'); tracker.render(str(d), quiet=True)
    page.goto(url + '/')
    with page.expect_navigation(): page.click('#send')
    assert comments(d)[0].get('sent_at')
    assert page.locator('#send').count() == 0 and 'sent to Claude' in page.inner_text('#i4 .cmt')
