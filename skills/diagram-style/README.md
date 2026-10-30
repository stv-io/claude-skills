# diagram-style

**Diagrams Claude draws come out looking like one consistent set, not a different sketch each time. The title states the conclusion, colour means a role, and there's one font and one set of shapes.**

![Reference figure: a client card, a region zone with a focus front-door card, a dashed cluster zone with gateway and pod cards, a shared-services hub, and other estates on the right, with a legend of every role and line style.](reference.png)

*The reference figure, drawn by `scripts/reference.py` straight from `tokens.json`. The diagrams in [this repo's READMEs](../../assets/diagrams) use the same style.*

Ask Claude for an architecture diagram and you get something different every time: hand-drawn fonts, random colours, a title that just names the topic. This skill gives Claude a short style guide ([STYLE.md](STYLE.md)) and every value in a machine-readable [tokens.json](tokens.json):

- **Colour by role, not vendor:** provider-managed blue, what you run green, the focus orange, a shared hub cyan, another estate pink, risk red, out of scope grey, later dashed. Three or four roles per figure.
- **Helvetica only, nothing below 13**, flat shapes, square-cornered arrows coloured by their source.
- **The figure frame:** a title that states the conclusion, subtitle, legend of only what's used, optional takeaway, and a provenance line for anything showing live infrastructure.
- **A checklist** before a figure is done, ending in "render it and look at the PNG".

## Install

```bash
npx skills add stv-io/claude-skills --skill diagram-style -g
```

## What you need

- **Python 3** for `reference.py` (standard library only).
- **An Excalidraw canvas** to draw on: [mcp_excalidraw](https://github.com/yctimlin/mcp_excalidraw) gives Claude a live canvas and an `export_to_image` tool. Without it, Claude can still write `.excalidraw` files you open at [excalidraw.com](https://excalidraw.com).
- Optional: skills that place official AWS or GCP icons. This style leaves icons to them.

## Use it

*"Draw the architecture of this service"*, *"make these diagrams look like the others"*, *"restyle this figure"*. Claude reads the guide, draws on the canvas, exports a PNG and checks it before calling it done.

To check the style on your own canvas:

```bash
python3 ~/.claude/skills/diagram-style/scripts/reference.py --post                  # adds the reference figure (doesn't clear the canvas)
python3 ~/.claude/skills/diagram-style/scripts/reference.py --out reference.excalidraw
```

## What it touches

- **Writes** only the figures you ask for. `--post` adds elements to the canvas at `http://127.0.0.1:3030` (change with `--canvas`) without clearing it.
- **Network:** only that local canvas.

## Update or remove

```bash
npx skills update diagram-style -g
npx skills remove diagram-style -g
```
