"""tracker.py serve: the /md route and the /feedback endpoint, over real HTTP."""
import json, urllib.error, urllib.request

import pytest

from conftest import comments


def get(url):
    try:
        with urllib.request.urlopen(url) as r: return r.status, r.read().decode()
    except urllib.error.HTTPError as e: return e.code, e.read().decode()


def post(url, body, ctype='application/json', origin=None, raw=None):
    data = raw if raw is not None else json.dumps(body).encode()
    req = urllib.request.Request(url + '/feedback', data=data, method='POST', headers={'Content-Type': ctype, **({'Origin': origin} if origin else {})})
    try:
        with urllib.request.urlopen(req) as r: return r.status, r.read().decode()
    except urllib.error.HTTPError as e: return e.code, e.read().decode()


def test_serves_page(server):
    url, _ = server
    code, body = get(url + '/')
    assert code == 200 and 'tracker-rev' in body


def test_md_served_as_text_without_mdserve(server):
    url, _ = server
    assert get(url + '/md?p=reports/r.md') == (200, '# r\n')


@pytest.mark.parametrize('p', ['../../../../etc/passwd', '/etc/hosts', 'status.json', 'missing.md', '../outside.md'])
def test_md_refuses_anything_but_markdown_inside_the_root(server, p):
    url, d = server
    (d.parent.parent / 'outside.md').write_text('secret')  # beyond the tmp tracker; not a git repo, so root = tracker dir
    assert get(url + '/md?p=' + p)[0] == 404


def test_post_comment_saves_and_rerenders(server):
    url, d = server
    code, body = post(url, {'item': '4', 'text': 'Go with B'}, origin=url)
    assert code == 201 and json.loads(body) == {'id': 1}
    assert comments(d)[0]['text'] == 'Go with B'
    assert 'Go with B' in get(url + '/')[1]


def test_general_comment(server):
    url, d = server
    assert post(url, {'item': None, 'text': 'General'})[0] == 201
    assert comments(d)[0]['item'] is None


@pytest.mark.parametrize('kwargs, code', [
    ({'body': {'item': '1', 'text': 'x'}, 'ctype': 'text/plain'}, 415),
    ({'body': {'item': '1', 'text': 'x'}, 'origin': 'https://evil.example'}, 403),
    ({'body': {'item': '99', 'text': 'x'}}, 400),
    ({'body': {'item': '1', 'text': ''}}, 400),
    ({'body': None, 'raw': b'not json'}, 400),
    ({'body': None, 'raw': b'[1, 2]'}, 400),
    ({'body': None, 'raw': json.dumps({'text': 'x' * 30000}).encode()}, 413),
])
def test_post_rejects_bad_requests(server, kwargs, code):
    url, d = server
    assert post(url, **kwargs)[0] == code
    assert comments(d) == []


def test_post_elsewhere_is_404(server):
    url, _ = server
    req = urllib.request.Request(url + '/status.json', data=b'{}', method='POST', headers={'Content-Type': 'application/json'})
    with pytest.raises(urllib.error.HTTPError) as e: urllib.request.urlopen(req)
    assert e.value.code == 404


def test_send_marks_comments_sent(server):
    url, d = server
    post(url, {'item': '1', 'text': 'a'}); post(url, {'item': None, 'text': 'b'})
    req = urllib.request.Request(url + '/feedback/send', data=b'{}', method='POST', headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as r: assert json.loads(r.read()) == {'sent': 2}
    assert all(c.get('sent_at') for c in comments(d))
    assert 'id="send"' not in get(url + '/')[1]


def test_send_refuses_cross_origin(server):
    url, d = server
    post(url, {'item': '1', 'text': 'a'})
    req = urllib.request.Request(url + '/feedback/send', data=b'{}', method='POST', headers={'Content-Type': 'application/json', 'Origin': 'https://evil.example'})
    with pytest.raises(urllib.error.HTTPError) as e: urllib.request.urlopen(req)
    assert e.value.code == 403 and not comments(d)[0].get('sent_at')
