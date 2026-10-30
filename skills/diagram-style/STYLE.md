# Diagram style guide

Architecture and infrastructure figures for documents read by engineers and
decision-makers. The look is flat and quiet: thin borders, pale fills, one
sans-serif font, colour that means something. A reader should get the point
from the title, confirm it from the shapes, and find the detail in the text.

Every value below is in [`tokens.json`](tokens.json). Change both together.

## 1. The figure frame

Every figure has the same outer parts, top to bottom:

| Part | Rule |
|---|---|
| **Title** | A sentence that states the conclusion, not the topic. "All external connections land on the hub", not "Network topology". Size 28, ink. |
| **Subtitle** | One line of scope or context: what is shown, which region, "CIDRs where known". Size 16, secondary. |
| **Legend** | One row of swatches, either under the subtitle or under the figure. Only the roles and line styles the figure actually uses. Size 14, secondary. |
| **Body** | Zones, cards and arrows. |
| **Takeaway** | Optional. One sentence under the body that says the thing the shapes can't, e.g. "Serving never routes to the data VPC: it reads through the provider APIs." Size 15, secondary. |
| **Provenance** | Required when the figure shows live infrastructure: "Verified 2026-10-09: zones and records via the AWS API." Absolute dates only. Size 13, secondary. |

Margins are 40px on every side. The title sits at (40, 40).

## 2. Colour: by role, not by vendor

Colours are Excalidraw's open-color palette, so a hand edit in the Excalidraw
picker lands on the same values. A colour says **what part a thing plays**.
Vendor identity comes from icons, not box colours.

| Role | Stroke | Fill | Use for |
|---|---|---|---|
| `managed` | `#1971c2` | `#e7f5ff` | Provider-managed services, public or internet-facing parts, the region or network the figure is about |
| `owned` | `#2f9e44` | `#ebfbee` | What we or the customer run; private or internal parts; healthy |
| `focus` | `#e8590c` | `#fff4e6` | The recommended option, or the one thing the figure is about. **At most one or two per figure** |
| `hub` | `#0c8599` | `#e3fafc` | Shared hub or landing point: transit, shared services, where connections terminate |
| `external` | `#c2255c` | `#fff0f6` | Another estate: other cloud, on-prem, DR site, third party |
| `automation` | `#7048e8` | `#f3f0ff` | Identity, controllers and cross-account links (external-dns, IAM roles, RAM shares) |
| `risk` | `#e03131` | `#fff5f5` | Blockers, open questions, cost hotspots. Chips and callouts, rarely whole boxes |
| `neutral` | `#1e1e1e` | `#ffffff` | The default card: a component with no special role |
| `outside` | `#868e96` | `#f1f3f5` | Out of scope: clients, users, systems we only talk to |
| `later` | `#868e96`, dashed | `#ffffff` | Later phase, optional, proposed, legacy |

Text and lines:

| Token | Value | Use for |
|---|---|---|
| `ink.text` | `#1e1e1e` | Titles, card titles, body text |
| `ink.secondary` | `#495057` | Subtitles, the last (qualifying) line of a card, legends, takeaways |
| `ink.muted_line` | `#868e96` | Neutral connectors, zone dividers, "later" borders |
| `ink.band` | `#f8f9fa` | Background bands (a region behind several zones) |

Rules:

- **Limit each figure to three or four roles** besides `neutral`. If a figure needs more, it is two figures.
- The same role keeps the same colour **across every figure in a set**. Write the mapping in the set's README if you specialise a role (e.g. "`owned` = run by the customer").
- Zone titles take their zone's stroke colour. Card titles are always ink.
- Never use colour alone to carry meaning: the legend names it, and dashed vs solid repeats it.

## 3. Type

- **One font: Helvetica, `fontFamily: 2`.** Never leave it unset. Excalidraw's default is the hand-drawn Virgil font, which reads as a sketch.
- **Excalidraw has no bold.** Build hierarchy from size and colour, not weight.
- Sizes:

| Role | Size |
|---|---|
| Title | 28 |
| Zone title, card title | 18 |
| Subtitle | 16 |
| Body text, takeaway | 15 |
| Arrow label, legend | 14 |
| Chip, provenance | 13 |

- Nothing below 13. If text doesn't fit at 13, the box is too small or the text is too long.
- Text in cards is **left-aligned**. Centre text only in chips and in one-line boxes with nothing else in them.
- Body rows are 24px apart at size 15.

## 4. Shapes

All elements: `roughness: 0`, `fillStyle: "solid"`, `opacity: 100`, rounded corners at a 10px radius (`roundness: {"type": 3, "value": 10}`; Excalidraw's adaptive default grows to 32px on large boxes).

### Zone

A boundary: region, network, account, cluster, environment.

- Stroke 2 in the role colour, fill in the role's pale fill. Nested zones go one step quieter: white or `ink.band` fill.
- The title is a **separate text element at the zone's top-left**, inset by the zone padding (24px), with an optional 26px icon before it. Never bind a label to a zone rectangle: Excalidraw centres it over everything inside.
- A dashed zone in `ink.muted_line` marks a grouping that isn't a boundary (a cluster's node pools, a logical tier).
- 24px between a zone's edge and anything inside it.

### Card

A component. Most of a figure is cards.

```
┌──────────────────────────────────┐
│ [icon] Card title                │  icon 32 at (x+14, y+14); title 18 at x+56
│ ┌──────────────────────────────┐ │
│ │           chip               │ │  optional: who runs it / what it is
│ └──────────────────────────────┘ │
│ body line                        │  15, ink, 24px rows
│ body line                        │
│ qualifying line                  │  last line in secondary: "Phase 2+", "to confirm"
└──────────────────────────────────┘
```

- `neutral` by default: ink stroke 1, white fill. Give a card a role colour only when the role is the point.
- The `focus` card gets stroke 2.
- 16px inner padding. Cards in a row share one height; same-role cards share one size.
- 40px between cards.

### Chip

A small full-width label inside a card that says who runs it or what kind of thing it is ("provider-managed", "we run it", "outside scope"). Height 30, stroke 1 and fill in the chip's role, text 13 centred in ink.

### Callout

A note that isn't a component: a `risk`- or `later`-styled box with secondary text, placed next to what it explains. Keep it to three lines.

## 5. Arrows and lines

- **Square corners.** Route with right angles (elbow arrows), never diagonals across the figure.
- Arrowhead: filled `triangle`. Use an arrowhead at both ends only for a genuinely two-way link.
- Width 2 for the flows the figure is about, 1 for secondary ones.
- **Colour follows the source's role** (a green spoke draws a green line to the hub). Neutral flows are ink. Links to later or optional things are `ink.muted_line`, dashed.
- Line style repeats the meaning: **solid** = exists or in scope now; **dashed** = later, optional, proposed, legacy; **dotted** = weak or same-account link.
- Connect box edge to box edge, not icon to icon. Keep at least 80px of visible line between shapes.
- Label sparingly, in 14 secondary, beside the line rather than on it. If every arrow needs a label, use a table.
- Route around zones, not through them. A line that crosses a box is a layout bug.

## 6. Icons

- Use the **official provider icon sets** (the `aws-diagrams` and `gcp-diagrams` skills place them; other providers' official SVGs otherwise). Never redraw a vendor icon.
- Sizes: 32 in cards, 26 in zone titles, 18 inline in a body line.
- An icon never replaces a label: every icon has text next to or under it.
- Provider skills may add their own conventions (account boxes, OU nesting). Those override this guide **for that provider's figures only**.

## 7. Layout

- 20px grid. Align edges; same-role shapes share a size.
- Flow left to right for request paths, top to bottom for hierarchy and fan-in (spokes above, hub below).
- Put the subject of the figure in the middle or the left; outside parties at the edges.
- Compare options as separate figures with identical geometry, so only the difference moves.
- Aim for a figure that reads at 1600px wide. Export at 2× (`tokens.export.scale`).

## 8. Before you call it done

1. The title states a conclusion.
2. Every role colour and line style used appears in the legend; nothing in the legend is unused.
3. All text is Helvetica, size 13 or larger.
4. No label bound to a zone; no arrow crossing a box.
5. Provenance line present if the figure shows live infrastructure.
6. Render it (`export_to_image`) and **look at the PNG** before committing it. Don't trust an export you haven't seen.
7. Commit the `.excalidraw` source next to the PNG (or the layout code that generates both).
