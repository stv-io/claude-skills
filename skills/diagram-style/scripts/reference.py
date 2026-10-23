#!/usr/bin/env python3
"""Draw the diagram-style reference figure from tokens.json.

One figure that uses every role, line style and text size in STYLE.md, so the
style can be checked on the real renderer. The primitives (zone, card, chip,
text, arrow) are also a starting point for new figures.

    python3 reference.py --out reference.excalidraw
    python3 reference.py --post [--dx N] [--dy N] [--canvas URL]

Standard library only. --post uses POST /api/elements/batch, which adds to the
canvas without clearing it.
"""
import argparse
import json
import pathlib
import random
import urllib.request

T = json.loads((pathlib.Path(__file__).resolve().parent.parent / "tokens.json").read_text())
F, INK, ROLE, EL, SP = T["font"], T["ink"], T["role"], T["element"], T["spacing"]
SIZE = F["size"]


class Figure:
    def __init__(self):
        self.els = []

    def _base(self, kind, x, y, w, h, **kw):
        e = dict(id=f"ds-{len(self.els):03d}", type=kind, x=x, y=y, width=w, height=h,
                 roughness=EL["roughness"], opacity=EL["opacity"], fillStyle=EL["fillStyle"],
                 strokeStyle="solid", seed=random.randint(1, 2**31))
        e.update(kw)
        self.els.append(e)
        return e

    def rect(self, x, y, w, h, role="neutral", sw=None, dash=None):
        r = ROLE[role]
        return self._base("rectangle", x, y, w, h, strokeColor=r["stroke"], backgroundColor=r["fill"],
                          strokeWidth=sw or EL["stroke_width"]["card"],
                          strokeStyle=dash or r.get("dash", "solid"), roundness=EL["roundness"])

    def text(self, x, y, s, size="body", color=None, align="left", w=None):
        fs = SIZE[size]
        lines = s.split("\n")
        tw = w or max(len(l) for l in lines) * fs * 0.56
        th = len(lines) * fs * F["line_height"]
        if align == "center":
            x -= tw / 2
        return self._base("text", x, y, tw, th, text=s, fontSize=fs, fontFamily=F["family"],
                          strokeColor=color or INK["text"], backgroundColor="transparent",
                          textAlign=align, verticalAlign="top")

    def arrow(self, pts, color=None, sw=None, dash="solid", both=False):
        x0, y0 = pts[0]
        rel = [[px - x0, py - y0] for px, py in pts]
        xs, ys = [p[0] for p in rel], [p[1] for p in rel]
        return self._base("arrow", x0, y0, max(xs) - min(xs), max(ys) - min(ys), points=rel,
                          strokeColor=color or INK["text"], backgroundColor="transparent",
                          strokeWidth=sw or EL["stroke_width"]["arrow"], strokeStyle=dash,
                          startArrowhead=EL["arrowhead"] if both else None,
                          endArrowhead=EL["arrowhead"], roundness=None)

    # composites -------------------------------------------------------------
    def zone(self, x, y, w, h, title, role="managed", dash=None, sw=None, quiet=False):
        r = ROLE[role]
        z = self.rect(x, y, w, h, role, sw=sw or EL["stroke_width"]["zone"], dash=dash)
        if quiet:
            z["backgroundColor"] = INK["white"]
        p = SP["zone_padding"]
        self.text(x + p, y + p - 4, title, "zone_title", r["stroke"])
        return z

    def chip(self, x, y, w, label, role):
        self.rect(x, y, w, 30, role, sw=EL["stroke_width"]["chip"])
        self.text(x + w / 2, y + 7, label, "chip", align="center")

    def card(self, x, y, w, h, title, rows, role="neutral", chip=None, last_secondary=True, sw=None):
        p = SP["card_padding"]
        self.rect(x, y, w, h, role, sw=sw)
        self.text(x + p, y + p, title, "card_title")
        ry = y + p + 34
        if chip:
            self.chip(x + p, ry, w - 2 * p, *chip)
            ry += 46
        for i, row in enumerate(rows):
            secondary = last_secondary and i == len(rows) - 1 and len(rows) > 1
            self.text(x + p, ry + i * SP["body_row"], row, "body", INK["secondary"] if secondary else None)

    def swatch(self, x, y, role, label):
        r = ROLE[role]
        self.rect(x, y, 28, 20, role, dash=r.get("dash"))
        self.text(x + 38, y + 1, label, "legend", INK["secondary"])

    def line_key(self, x, y, dash, label):
        self.arrow([(x, y + 10), (x + 56, y + 10)], INK["text"] if dash == "solid" else INK["muted_line"],
                   dash=dash)
        self.text(x + 68, y + 1, label, "legend", INK["secondary"])


def reference():
    f = Figure()
    m = SP["margin"]
    f.text(m, m, "The managed front door takes the traffic; everything behind it is ours", "title")
    f.text(m, m + 44, "Reference figure for the diagram-style guide · every role, line style and text size",
           "subtitle", INK["secondary"])

    # legend row
    lx, ly = m, 130
    for role, label in [("managed", "provider-managed"), ("owned", "we run it"), ("focus", "recommended"),
                        ("hub", "shared hub"), ("external", "other estate"), ("risk", "open question"),
                        ("outside", "outside scope")]:
        f.swatch(lx, ly, role, label)
        lx += 52 + len(label) * 8
    f.line_key(lx + 10, ly, "solid", "now")
    f.line_key(lx + 150, ly, "dashed", "later or optional")

    # client, outside the region
    f.card(m, 300, 220, 200, "Clients", ["browsers and partners", "~500k RPS", "peak 1.3× mean"],
           chip=("outside scope", "outside"))

    # the region
    f.zone(300, 190, 1000, 520, "region-1 · 10.0.0.0/16")
    f.card(330, 300, 270, 200, "Front door", ["regional L4 load balancer", "one VIP, no proxy", "Premium tier if measured"],
           role="focus", chip=("provider-managed", "managed"), sw=EL["stroke_width"]["focus_card"])
    f.zone(640, 250, 630, 290, "Cluster, multi-zone", role="outside", dash="dashed",
           sw=EL["stroke_width"]["card"], quiet=True)
    f.card(664, 300, 270, 200, "Gateway", ["L7 routing by hostname", "20–30 hostnames", "deployed by CI"],
           chip=("we run it", "owned"))
    f.card(974, 300, 270, 200, "Service pods", ["one pod per node", "Spot, two zones", "capacity to confirm"],
           chip=("we run it", "owned"))
    f.card(330, 580, 940, 100, "Shared services hub", ["DNS forwarding · egress · private endpoints"],
           role="hub", last_secondary=False)

    # other estates, right
    f.card(1340, 190, 260, 170, "Second region", ["same pattern", "own address range", "Phase 2+"], role="later")
    f.card(1340, 400, 260, 170, "Other cloud", ["HA VPN, 4 tunnels", "BGP", "Phase 1"], role="external")
    f.card(1340, 600, 260, 110, "Open question", ["return-path volume", "decides the link size"], role="risk")

    # flows
    f.arrow([(260, 400), (330, 400)])                                   # clients -> front door
    f.arrow([(600, 400), (664, 400)], ROLE["focus"]["stroke"])         # front door -> gateway
    f.arrow([(934, 400), (974, 400)], ROLE["owned"]["stroke"])         # gateway -> pods
    f.arrow([(1109, 500), (1109, 580)], ROLE["owned"]["stroke"], sw=EL["stroke_width"]["arrow_secondary"])
    f.arrow([(1270, 630), (1305, 630), (1305, 485), (1340, 485)], ROLE["hub"]["stroke"], both=True)
    f.arrow([(1300, 275), (1340, 275)], INK["muted_line"], dash="dashed")   # region edge -> later
    f.text(1120, 550, "egress", "arrow_label", INK["secondary"])

    f.text(m, 750, "Two hops before the pod: the load balancer forwards packets; the gateway terminates and routes.",
           "footer", INK["secondary"])
    f.text(m, 780, "Illustrative only: no live infrastructure. Generated by diagram-style/scripts/reference.py.",
           "provenance", INK["secondary"])
    return f.els


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", help="write an .excalidraw file")
    ap.add_argument("--post", action="store_true", help="add to the live canvas")
    ap.add_argument("--canvas", default="http://127.0.0.1:3030")
    ap.add_argument("--dx", type=float, default=0)
    ap.add_argument("--dy", type=float, default=0)
    a = ap.parse_args()
    els = reference()
    for e in els:
        e["x"] += a.dx
        e["y"] += a.dy
    if a.out:
        scene = dict(type="excalidraw", version=2, source="diagram-style", elements=els,
                     appState=dict(viewBackgroundColor=T["export"]["background"]), files={})
        pathlib.Path(a.out).write_text(json.dumps(scene, indent=1))
        print(f"wrote {a.out} ({len(els)} elements)")
    if a.post:
        req = urllib.request.Request(f"{a.canvas}/api/elements/batch", method="POST",
                                     data=json.dumps({"elements": els}).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as r:
            print(f"posted {len(els)} elements: HTTP {r.status}")
    if not (a.out or a.post):
        ap.error("give --out and/or --post")


if __name__ == "__main__":
    main()
