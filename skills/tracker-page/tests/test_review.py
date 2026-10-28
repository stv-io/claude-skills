"""review.py without a browser: the diff, the summary parser and the approvals round trip."""
import json, re

import pytest

import review


def test_sbs_marks_words_and_counts():
    L, R, I, add, rem = review.sbs('the old cat', 'the new cat')
    assert L == 'the <del>old</del> cat' and R == 'the <ins>new</ins> cat'
    assert '<del>old</del><ins>new</ins>' in I and (add, rem) == (1, 1)


def test_sbs_escapes():
    L, R, *_ = review.sbs('<b>', '<i>')
    assert '<b>' not in L and '&lt;i&gt;' in R


@pytest.fixture
def cards(tmp_path):
    p = tmp_path / 'cards.json'
    p.write_text(json.dumps({'title': 'Cell review', 'groups': [
        {'name': 'Acme', 'cards': [
            {'id': 'D1', 'heading': 'D1 · Scope', 'before': 'old', 'after': 'new', 'context': 'req'},
            {'id': 'D2', 'before': 'same', 'after': 'same'}]},
        {'name': 'Bizi Box', 'cards': [{'id': 'O1', 'before': '', 'after': 'added'}]}]}))
    return p


def test_build_pages(cards, tmp_path):
    out = tmp_path / 'out'; review.build(cards, out)
    acme = (out / 'acme.html').read_text()
    assert (out / 'bizi-box.html').exists() and (out / 'index.html').exists()
    unch = acme.split('class="unch"')[1]
    assert 'data-ref="Acme / D2"' in unch and 'data-ref="Acme / D1"' not in unch  # unchanged card folded away
    assert 'id="allunch"' in acme and 'data-key="rv-cell-review-acme"' in acme
    assert '<i>(empty)</i>' in (out / 'bizi-box.html').read_text()


def test_record_round_trip(cards, tmp_path):
    out, ap, summary = tmp_path / 'out', tmp_path / 'approvals.json', tmp_path / 's.txt'
    summary.write_text('Acme / D1: approve — fine\nAcme / D2: hold — check wording\nBizi Box / O1: unreviewed\nnoise line\n')
    review.record(ap, summary)
    assert json.loads(ap.read_text()) == {'approved': ['Acme / D1'], 'held': ['Acme / D2'], 'notes': {'Acme / D1': 'fine', 'Acme / D2': 'check wording'}}
    review.build(cards, out, ap)
    board = (out / 'index.html').read_text()
    assert '1 of 3 approved (33%) · 1 held' in board
    acme = (out / 'acme.html').read_text()
    assert re.search(r'data-ref="Acme / D1" data-state="approve"', acme) and '>Approved</span>' in acme
    summary.write_text('Acme / D2: approved\n')  # a later round flips a held card
    review.record(ap, summary)
    assert json.loads(ap.read_text())['held'] == []
