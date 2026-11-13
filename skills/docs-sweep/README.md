# docs-sweep

Before a branch becomes a PR, Claude sweeps the whole repo's docs for everything the change made untrue, not only the lines the diff touched.

Claude first lists what the change changes, as facts (old value, new value). A small script then finds candidates, and Claude judges each one: stale (fix it in this branch), still true, history (a changelog or decision record: leave it), or wrong before this change (report it as a follow-up). It ends with a short report of what it fixed, what it left and why, and what it couldn't check.

- **Needs:** Python 3.9 or later, git.
- **Touches:** the script only reads. Claude edits the docs it finds stale, in the branch under review.

```bash
bin/docs-sweep all [BASE]     # all three checks; BASE defaults to origin/HEAD
bin/docs-sweep terms [BASE]   # values the change removed that the repo still mentions
bin/docs-sweep paths          # `a/b` paths named in Markdown that don't exist
bin/docs-sweep links          # relative links and #anchors that don't resolve
```

`terms` compares the merge base with the working tree, so uncommitted edits count, and new files that aren't ignored are checked too. Exit code 1 means something to look at, 2 means git failed (a bad BASE, or not a repo).

## Tests

```bash
cd skills/docs-sweep/tests
uv run --no-project --with pytest pytest -q
```

Each test builds a throwaway git repo, makes a change and runs the script against it.
