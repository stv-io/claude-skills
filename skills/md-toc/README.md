# md-toc

Long Markdown documents get a TL;DR, a short Summary and a table of contents whose links work.

Claude writes the TL;DR and Summary. A small script builds the TOC from the headings, using the same anchor rules as GitHub (punctuation and emoji dropped, repeated headings numbered `-1`, `-2`). It also writes the anchor into each heading (`## <a id="setup"></a>Setup`), so the links work in viewers that don't make heading ids themselves, mdserve for example, as well as on GitHub. It then checks every in-page `#link` in the file and reports `file:line` for any that point nowhere. `--github` goes one step further: it renders the file with GitHub's own API and confirms each anchor exists in the real output.

- **Needs:** Python 3. For `--github`, the `gh` CLI must be logged in.
- **Touches:** rewrites the file you point it at. It changes the block between `<!-- toc -->` and `<!-- tocstop -->` (inserting it once if missing) and the anchor tags at the start of headings. `--github` sends the file's text to api.github.com.

```bash
bin/md-toc doc.md            # write/refresh TOC, check links
bin/md-toc doc.md --check    # check only (exit 1 on a broken anchor)
bin/md-toc doc.md --github   # verify against GitHub's renderer
```

## Tests

```bash
cd skills/md-toc/tests
uv run --no-project --with pytest --with markdown pytest -q -rs
```

The unit tests need nothing else. The renderer tests check that every `#link` in the rendered HTML has a target in Python-Markdown (which makes no heading ids), in [mdserve](https://github.com/jfernandez/mdserve) if it's on your PATH, and in GitHub's renderer if `gh` is logged in. Each skips when its renderer is missing. CI installs all three and sets `MD_TOC_REQUIRE_RENDERERS=1`, so there a skip counts as a failure.
