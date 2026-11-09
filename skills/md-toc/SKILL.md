---
name: md-toc
description: Give a long Markdown document a reader-first header, with a one-line TL;DR, a short Summary and a table of contents whose links actually work. The TOC is generated from the headings with GitHub-compatible anchors and every in-page link is checked. Use for "/md-toc", "add a TOC", "table of contents", "add a TL;DR / summary to this doc", "the TOC links are broken", "fix the anchors". Also use, without being asked, as the last step when writing or substantially editing any Markdown file that is long by the rule below.
---

# md-toc

Claude writes the TL;DR and the Summary. The script writes the table of contents and checks the links. **Never type TOC entries or `#anchors` by hand.** Hand-made anchors are how TOCs break (`&`, `:`, backticks, emoji, repeated headings). The script is `bin/md-toc` in this skill's folder.

```bash
md-toc FILE --stats      # {"words": N, "headings": {...}, "has_toc": bool}
md-toc FILE              # write/refresh the TOC in place, then check every #link
md-toc FILE --check      # check only; exit 1 and file:line for each broken anchor
md-toc FILE --github     # also render via GitHub's API and confirm each anchor exists
```

Options: `--min-level 2 --max-level 3` (default: H2 and H3), `--title Contents`.

## When a document gets the treatment

Run `--stats`. Add the TL;DR, Summary and TOC if **either** is true:

- 600 words or more, or
- 4 or more H2 headings.

Below that, leave the document alone unless the user asks. If they ask for the header on a short doc, do it.

## Layout

```markdown
# Title

**TL;DR:** One or two sentences: the conclusion or the ask, not the topic.

## Summary

3–6 bullets or one short paragraph. What the document says, decides or asks for,
with the key numbers and dates. Someone who reads only this should be able to act.

## Contents

<!-- toc -->
<!-- tocstop -->

## First real section
...
```

- There is exactly one H1. If the doc has several H1s, demote the extra ones to H2 (and shift their children down a level) before generating, otherwise the TOC nesting is wrong.
- Write the TL;DR and Summary from the body you have just read. Don't invent anything the body doesn't say. Use the doc's own language and figures.
- If a TL;DR or Summary already exists, update it in place. Never add a second one.
- If the document already has an intro paragraph under the title, keep it between the TL;DR and `## Summary`. Don't let it end up between the Summary and the Contents.
- The markers can go anywhere. Without them, the script adds `## Contents` before the first H2 that isn't the TL;DR or Summary.
- The `Contents` heading itself is left out of the TOC. `Summary` stays in.
- Headings get an `<a id="…"></a>` tag in the source. That's deliberate and needed. See below.

## Steps

1. `md-toc FILE --stats` and decide using the rule above.
2. Read the document. Write or refresh the TL;DR and Summary at the top.
3. `md-toc FILE`. This writes the TOC, adds the heading anchors (see below) and checks every `](#…)`, `href="#…"` and `[ref]: #…` link in the file. Re-running it replaces the TOC rather than adding another.
4. If it reports a broken anchor, fix the **link**, not the TOC (the hint `did you mean #…` usually names the right slug), then run it again. Done means exit 0.
5. When the file is going to GitHub or a customer and isn't sensitive, add `--github` for proof against the real renderer. It sends the file's text to api.github.com, so skip it for client-confidential documents and say you skipped it.
6. Tell the user how many TOC entries were written, that the links check clean, and whether the GitHub render was verified.

## Where the links work

Many viewers never give headings an id. mdserve 1.1.0 is one: it renders `<h2>Background</h2>`, so a `#background` link has nothing to jump to. To cover them, the script writes the anchor into every heading the TOC or a body link points at:

```markdown
## <a id="background"></a>Background
```

The anchor names follow GitHub's rules (github-slugger), so GitHub, GitLab, VS Code and mdserve all jump to the same place, and the tag doesn't show. The script rewrites these tags on every run, so renaming a heading moves its anchor too. `--check` fails on any link that only works where the viewer makes its own heading ids. `--no-anchors` leaves the tags out, for GitHub-only documents where clean source matters more.

These still won't work:

- **Viewers that strip raw HTML**, such as Bitbucket, which also prefixes its own ids with `markdown-header-`. If the doc lives there, say so. Don't hand-patch the anchors.
- **PDF via pm-render or markdown-to-pdf**: the anchors work if the converter keeps HTML ids. Check one link in the output.

If headings change later, run `md-toc FILE` again. The TOC and the anchors are regenerated, and the check catches any body link that still points at the old heading text.
