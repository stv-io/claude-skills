"""md-toc without any external renderer: slugs, TOC writing, anchors, the link check."""
import json

import pytest

from conftest import mdtoc, run


# Every expected value here was confirmed against GitHub's own renderer
# (POST /markdown); test_renderers.py re-checks them live when it can.
@pytest.mark.parametrize("heading, want", [
    ("Setup & Install", "setup--install"),
    ("Step 1: `kubectl` config (v1.2.3)", "step-1-kubectl-config-v123"),
    ("What's new in **2026**? 🚀", "whats-new-in-2026-"),
    ("snake_case and _emphasis_ heading", "snake_case-and-emphasis-heading"),
    ("[Linked](https://example.com) heading with <code>html</code>", "linked-heading-with-html"),
    ("Ünïcödé — dashes – here", "ünïcödé--dashes--here"),
    ("Step 1: Control plane 1.29 → 1.30", "step-1-control-plane-129--130"),
    ("CoreDNS 🐢 slow to settle", "coredns--slow-to-settle"),
    ("Can we skip 1.30?", "can-we-skip-130"),
    (r"Escaped \*stars\*", "escaped-stars"),
])
def test_slug_matches_github(heading, want):
    assert mdtoc.slug(mdtoc.plain(heading)) == want


def test_repeated_headings_are_numbered():
    lines = ["## FAQ", "## FAQ", "## FAQ-1", "## FAQ"]
    assert [h["slug"] for h in mdtoc.headings(lines)] == ["faq", "faq-1", "faq-1-1", "faq-2"]


def test_code_fences_front_matter_and_setext(doc):
    hs = mdtoc.headings(doc("tricky.md").read_text().split("\n"))
    texts = [h["text"] for h in hs]
    assert "not a heading" not in " ".join(texts)
    assert "front matter is not a heading" not in texts
    assert ("Setext Heading", 2) in [(h["text"], h["level"]) for h in hs]


def test_inserts_contents_after_summary(doc):
    p = doc("runbook.md")
    code, _, err = run(p)
    assert code == 0, err
    text = p.read_text()
    lines = text.split("\n")
    contents = next(i for i, l in enumerate(lines) if l.endswith("Contents"))
    summary_or_first = next(i for i, l in enumerate(lines) if l.startswith("## ") and i != contents)
    # no summary in this fixture: Contents goes before the first H2
    assert contents < summary_or_first
    toc = text.split("<!-- toc -->")[1].split("<!-- tocstop -->")[0]
    assert "(#contents)" not in toc                       # doesn't list itself
    assert "- [Background](#background)" in toc
    assert "  - [Access & permissions](#access--permissions)" in toc   # H3 nested
    assert toc.count("\n- ") == 8 and toc.count("\n  - ") == 12


def test_summary_is_listed_and_contents_follows_it(tmp_path):
    p = tmp_path / "d.md"
    p.write_text("# T\n\n**TL;DR:** x\n\n## Summary\n\ns\n\n## One\n\n## Two\n")
    assert run(p)[0] == 0
    text = p.read_text()
    assert text.index("Summary") < text.index("Contents") < text.index("</a>One")
    assert "- [Summary](#summary)" in text


def test_existing_markers_are_used(tmp_path):
    p = tmp_path / "d.md"
    p.write_text("# T\n\n## Here\n\n<!-- toc -->\nstale\n<!-- tocstop -->\n\n## A\n")
    assert run(p)[0] == 0
    text = p.read_text()
    assert "stale" not in text and "- [A](#a)" in text
    assert text.count("<!-- toc -->") == 1


def test_idempotent(doc):
    p = doc("tricky.md")
    run(p)
    first = p.read_text()
    code, _, err = run(p)
    assert code == 0 and "unchanged" in err
    assert p.read_text() == first


def test_headings_get_explicit_anchors(doc):
    p = doc("tricky.md")
    run(p)
    text = p.read_text()
    assert '## <a id="setup--install"></a>Setup & Install' in text
    assert '<a id="setext-heading"></a>Setext Heading\n------' in text
    assert '## not a heading' in text                      # fenced code untouched
    assert '<a id="too-deep-for-the-toc">' not in text     # H4: not in TOC, not linked
    # anchor tags don't leak into the TOC's link text
    assert "- [Setup & Install](#setup--install)" in text


def test_renamed_heading_moves_anchor_and_stale_body_link_fails(tmp_path):
    p = tmp_path / "d.md"
    p.write_text("# T\n\nSee [old](#old-name).\n\n## Old name\n\n## Other\n")
    assert run(p)[0] == 0
    p.write_text(p.read_text().replace("Old name", "New name"))
    code, out, _ = run(p)
    text = p.read_text()
    assert '<a id="new-name"></a>New name' in text
    assert 'id="old-name"' not in text
    assert code == 1 and "broken anchor #old-name" in out


def test_check_reports_broken_link_with_line_and_hint(tmp_path):
    p = tmp_path / "d.md"
    p.write_text("# T\n\n## Set up\n\nsee [x](#setup)\n")
    code, out, _ = run(p, "--check", "--no-anchors")
    assert code == 1
    assert "d.md:5: broken anchor #setup (did you mean #set-up?)" in out


def test_check_fails_on_link_without_explicit_anchor(tmp_path):
    p = tmp_path / "d.md"
    p.write_text("# T\n\n- [A](#a)\n\n## A\n")
    code, out, _ = run(p, "--check")
    assert code == 1 and "has no <a id>" in out
    assert run(p, "--check", "--no-anchors")[0] == 0   # fine for GitHub-only docs


def test_html_ids_and_names_count_as_targets(tmp_path):
    p = tmp_path / "d.md"
    p.write_text('# T\n\n[a](#custom) [b](#old)\n\n<a name="old"></a>\n<span id="custom">x</span>\n')
    assert run(p, "--check")[0] == 0


def test_links_inside_code_are_ignored(tmp_path):
    p = tmp_path / "d.md"
    p.write_text("# T\n\n`[x](#nope)`\n\n```\n[y](#nope)\n```\n")
    assert run(p, "--check")[0] == 0


def test_no_anchors_option(doc):
    p = doc("tricky.md")
    assert run(p, "--no-anchors")[0] == 0
    assert "<a id=" not in p.read_text()


def test_level_options(doc):
    p = doc("tricky.md")
    run(p, "--max-level", "4")
    assert "(#too-deep-for-the-toc)" in p.read_text()


def test_print_does_not_write(doc):
    p = doc("tricky.md")
    before = p.read_text()
    code, out, _ = run(p, "--print")
    assert code == 0 and "- [FAQ](#faq-1)" in out
    assert p.read_text() == before


def test_stats(doc):
    code, out, _ = run(doc("runbook.md"), "--stats")
    s = json.loads(out)
    assert code == 0 and s["headings"]["2"] == 8 and s["headings"]["3"] == 12
    assert s["words"] > 600 and s["has_toc"] is False
