# README diagrams

Drawn in the [diagram-style](../../skills/diagram-style) house style by `figures.py`. Role mapping for this set: `outside` = you, `managed` = Claude / Claude Code, `owned` = what runs on your machine, `focus` = the thing the figure is about.

To change a figure, edit `figures.py`, then:

```bash
python3 assets/diagrams/figures.py --out assets/diagrams          # refresh the .excalidraw sources
python3 assets/diagrams/figures.py --post --dy 3000               # add to a live canvas, below other work
```

Export each figure with the Excalidraw MCP `export_to_image` tool (PNG, scale 2, padding 40), passing its element ids (`rd-<name>-NNN`), so nothing else on the canvas is included. Look at every PNG before committing it.
