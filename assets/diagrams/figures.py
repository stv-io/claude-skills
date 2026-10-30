#!/usr/bin/env python3
"""Draw the README figures in the diagram-style house style.

    python3 assets/diagrams/figures.py --out assets/diagrams          # one .excalidraw per figure
    python3 assets/diagrams/figures.py --post [--canvas URL] [--dy N]  # add them to a live canvas

Uses the primitives and tokens from skills/diagram-style. Element ids are
prefixed per figure (rd-<name>-NNN) so a figure can be exported on its own
with the Excalidraw MCP export_to_image tool (elementIds), without touching
anything else on the canvas.

Role mapping for this set: `outside` = you, `managed` = Claude / Claude Code,
`owned` = what runs on your machine, `focus` = the thing the figure is about.
"""
import argparse
import importlib.util
import json
import pathlib
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("ds", ROOT / "skills/diagram-style/scripts/reference.py")
ds = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ds)
Figure, ROLE, INK, EL, SP = ds.Figure, ds.ROLE, ds.INK, ds.EL, ds.SP
M = SP["margin"]
FOCUS_SW = EL["stroke_width"]["focus_card"]


def card_h(rows, chip=True):
    return SP["card_padding"] * 2 + 34 + (46 if chip else 0) + len(rows) * SP["body_row"]


def frame(f, title, subtitle, legend, lines=()):
    f.text(M, M, title, "title")
    f.text(M, M + 44, subtitle, "subtitle", INK["secondary"])
    x, y = M, 130
    for role, label in legend:
        f.swatch(x, y, role, label)
        x += 56 + len(label) * 7.2
    for dash, label in lines:
        f.line_key(x + 10, y, dash, label)
        x += 96 + len(label) * 7.2


def browser_select():
    f = Figure()
    frame(f, "Claude asks which browser before it acts, then keeps your answer",
          "browser-select: friendly names for the browsers connected to Claude in Chrome",
          [("outside", "you"), ("managed", "Claude"), ("owned", "this skill, on your machine"), ("focus", "the browser you chose")])
    top = 200
    you = ["names a browser,", "or picks one when asked"]
    f.card(M, top + 60, 260, card_h(you), "You", you, role="outside", chip=("outside the skill", "outside"), last_secondary=False)
    cl = ["1  browsers list", "2  list_connected_browsers", "3  asks: which one?", "4  select_browser(deviceId)"]
    f.card(460, top + 40, 320, card_h(cl), "Claude", cl, role="managed", chip=("Claude Code", "managed"), last_secondary=False)
    reg = ["~/.claude/browsers.json", "work-chrome  → 3f6c…", "personal-dia → 9b1e…", "work-dia     → c2d8…"]
    f.card(460, top + 360, 320, card_h(reg), "browsers CLI", reg, role="owned", chip=("in this skill", "owned"), last_secondary=False)
    zx, zy, zw = 920, top, 420
    f.zone(zx, zy, zw, 520, "Claude in Chrome", role="managed")
    bw = zw - 2 * SP["zone_padding"]
    f.card(zx + 24, zy + 70, bw, card_h(["work Google account, Jira"], chip=False), "work-chrome", ["work Google account, Jira"],
           role="focus", sw=FOCUS_SW, last_secondary=False)
    f.card(zx + 24, zy + 230, bw, card_h(["personal logins only"], chip=False), "personal-dia", ["personal logins only"], last_secondary=False)
    f.card(zx + 24, zy + 390, bw, card_h(["client tenant"], chip=False), "work-dia", ["client tenant"], last_secondary=False)
    # flows
    f.arrow([(300, top + 150), (460, top + 150)])
    f.text(316, top + 120, "\"check my board\"", "arrow_label", INK["secondary"])
    f.arrow([(620, top + 40 + card_h(cl)), (620, top + 360)], ROLE["managed"]["stroke"], both=True)
    f.text(632, top + 300, "get work-chrome → deviceId", "arrow_label", INK["secondary"])
    f.arrow([(780, top + 120), (944, top + 120)], ROLE["managed"]["stroke"])
    f.text(792, top + 90, "select_browser", "arrow_label", INK["secondary"])
    f.text(M, top + 600, "Without a name from you, Claude asks: one registered default is not permission to pick. The answer holds for the session.",
           "footer", INK["secondary"])
    return f.els


def claude_usage():
    f = Figure()
    frame(f, "Your status line feeds the cache; Claude reads it before big runs",
          "claude-usage: the 5-hour and weekly plan limits, which Claude Code passes only to the status-line command",
          [("managed", "Claude Code"), ("owned", "on your machine"), ("focus", "the cache"), ("risk", "keep in mind")])
    y1, w, gap = 210, 300, 80
    s = ["passes rate_limits to the", "status line on every refresh"]
    f.card(M, y1, w, card_h(s), "Claude Code session", s, role="managed", chip=("interactive only", "managed"), last_secondary=False)
    sl = ["~/.claude/statusline.sh", "one added line pipes", "its input to the capture"]
    f.card(M + w + gap, y1, w, card_h(sl), "Your status line", sl, role="owned", chip=("you add one line", "owned"), last_secondary=False)
    cp = ["merges per window:", "newest reset wins,", "never writes bad data"]
    f.card(M + 2 * (w + gap), y1, w, card_h(cp), "claude-usage-capture", cp, role="owned", chip=("in this skill", "owned"), last_secondary=False)
    ca = ["5h: 31%, resets 15:00", "7d: 59%, resets Sun", "stale after 5 minutes"]
    cx = M + 3 * (w + gap)
    f.card(cx, y1, w, card_h(ca), "~/.claude/usage-cache.json", ca, role="focus", sw=FOCUS_SW, chip=("one small file", "focus"))
    y2 = y1 + 300
    rd = ["claude-usage", "claude-usage --json", "exit 2 when stale"]
    f.card(cx, y2, w, card_h(rd), "claude-usage", rd, role="owned", chip=("in this skill", "owned"))
    ask = ["before a fan-out or workflow:", "5h ≥ 80% or 7d ≥ 90%", "→ tell you, ask first"]
    f.card(M + 2 * (w + gap), y2, w, card_h(ask), "Claude decides", ask, role="managed", chip=("Claude Code", "managed"), last_secondary=False)
    f.card(M + w + gap, y2 + 30, w, card_h(["account-wide: every session", "and subagent shares them"], chip=False),
           "Limits are shared", ["account-wide: every session", "and subagent shares them"], role="risk", last_secondary=False)
    h = card_h(s)
    for i in range(3):
        a = M + (i + 1) * w + i * gap
        f.arrow([(a, y1 + h / 2), (a + gap, y1 + h / 2)], ROLE["managed" if i == 0 else "owned"]["stroke"])
    f.arrow([(cx + w / 2, y1 + card_h(ca)), (cx + w / 2, y2)], ROLE["focus"]["stroke"])
    f.text(cx + w / 2 + 12, y1 + card_h(ca) + 24, "reads", "arrow_label", INK["secondary"])
    f.arrow([(cx, y2 + card_h(rd) / 2), (cx - gap, y2 + card_h(rd) / 2)], ROLE["owned"]["stroke"])
    f.text(M, y2 + 250, "No hook, no data: headless claude -p runs don't run the status line, so the cache only moves while a session is open.",
           "footer", INK["secondary"])
    return f.els


def session_export():
    f = Figure()
    frame(f, "Only what you asked and what Claude answered goes into the export",
          "session-export: a Claude Code session transcript turned into shareable Markdown",
          [("owned", "on your machine"), ("focus", "session-export"), ("outside", "left out"), ("risk", "check before sharing")])
    y, w = 260, 300
    tr = ["~/.claude/projects/<project>/", "<session>.jsonl", "everything from the session"]
    f.card(M, y + 70, w, card_h(tr), "Session transcript", tr, role="owned", chip=("read only", "owned"), last_secondary=False)
    se = ["--prompts to pick a range", "--from / --to, --title", "reports what it masked"]
    f.card(M + w + 80, y + 70, w, card_h(se), "session-export", se, role="focus", sw=FOCUS_SW, chip=("in this skill", "focus"), last_secondary=False)
    ox = M + 2 * (w + 80)
    keep = ["numbered prompts", "Claude's answers, as written", "one line per tool call"]
    f.card(ox, y - 40, w, card_h(keep, chip=False), "Kept", keep, role="owned", last_secondary=False)
    drop = ["thinking, tool output,", "subagent transcripts,", "system reminders"]
    f.card(ox, y + 130, w, card_h(drop, chip=False), "Left out", drop, role="outside", last_secondary=False)
    mask = ["home folder → ~", "known token formats,", "*_TOKEN= values → «redacted»"]
    f.card(ox, y + 300, w, card_h(mask, chip=False), "Masked (best-effort)", mask, role="risk", last_secondary=False)
    out = ["contents list, outcomes,", "files written, links", "read it before you share it"]
    f.card(ox + w + 80, y + 70, w, card_h(out), "shareable .md", out, role="owned", chip=("the file you name", "owned"))
    mid = y + 70 + card_h(tr) / 2
    f.arrow([(M + w, mid), (M + w + 80, mid)], ROLE["owned"]["stroke"])
    sx = M + 2 * w + 80
    kept_y, drop_y, mask_y = y - 40 + 60, y + 130 + 60, y + 300 + 60
    f.arrow([(sx, mid - 40), (sx + 30, mid - 40), (sx + 30, kept_y), (ox, kept_y)], ROLE["owned"]["stroke"])
    f.arrow([(sx, mid), (sx + 50, mid), (sx + 50, drop_y), (ox, drop_y)], ROLE["outside"]["stroke"], dash="dashed")
    f.arrow([(sx, mid + 40), (sx + 30, mid + 40), (sx + 30, mask_y), (ox, mask_y)], ROLE["risk"]["stroke"])
    f.arrow([(ox + w, kept_y), (ox + w + 40, kept_y), (ox + w + 40, mid - 40), (ox + w + 80, mid - 40)], ROLE["owned"]["stroke"])
    f.arrow([(ox + w, mask_y), (ox + w + 40, mask_y), (ox + w + 40, mid + 40), (ox + w + 80, mid + 40)], ROLE["risk"]["stroke"])
    f.text(M, y + 470, "Tool output never reaches the export, so a secret Claude only read stays out. Masking catches common formats, not all of them.",
           "footer", INK["secondary"])
    return f.els


def mac_disk_cleanup():
    f = Figure()
    frame(f, "Nothing is deleted until you approve it, and every step is measured",
          "mac-disk-cleanup (macOS only): one agreed step at a time, logged in a tracker page",
          [("outside", "you"), ("owned", "this skill, on your machine"), ("focus", "the guarded step"), ("risk", "refused")],
          [("solid", "each step"), ("dashed", "next candidate")])
    y1, w, gap = 210, 300, 80
    b = ["APFS containers, free space,", "local snapshots,", "biggest folders (dust)"]
    f.card(M, y1, w, card_h(b), "1  Baseline", b, role="owned", chip=("read-only", "owned"), last_secondary=False)
    p = ["biggest first, by tier:", "caches · tool data ·", "personal files · git"]
    f.card(M + w + gap, y1, w, card_h(p), "2  Propose", p, role="owned", chip=("Claude", "owned"), last_secondary=False)
    a = ["caches: one OK can cover", "a batch; personal files:", "always one at a time"]
    f.card(M + 2 * (w + gap), y1, w, card_h(a), "3  You approve", a, role="outside", chip=("you", "outside"), last_secondary=False)
    r = ["df before → run → df after", "--delete refuses: symlinks,", "outside ~, top-level folders"]
    rx = M + 3 * (w + gap)
    f.card(rx, y1, w, card_h(r), "4  run_step.py", r, role="focus", sw=FOCUS_SW, chip=("guarded", "focus"), last_secondary=False)
    y2 = y1 + 320
    lg = ["item: done or blocked", "measured GiB change", "report kept per step"]
    f.card(M + 2 * (w + gap), y2, w, card_h(lg), "5  Tracker page", lg, role="owned", chip=("tracker-page", "owned"), last_secondary=False)
    rf = ["~/Library, ~/Documents, ~/.ssh,", "anything outside ~, symlinks", "→ logged as blocked"]
    f.card(rx, y2, w, card_h(rf, chip=False), "Refused", rf, role="risk", last_secondary=False)
    h = card_h(b)
    roles = ["owned", "owned", "outside"]
    for i in range(3):
        x0 = M + (i + 1) * w + i * gap
        f.arrow([(x0, y1 + h / 2), (x0 + gap, y1 + h / 2)], ROLE[roles[i]]["stroke"])
    f.text(M + 3 * w + 2 * gap + 12, y1 + h / 2 - 30, "approved", "arrow_label", INK["secondary"])
    f.arrow([(rx + w - 60, y1 + card_h(r)), (rx + w - 60, y2)], ROLE["risk"]["stroke"], sw=EL["stroke_width"]["arrow_secondary"])
    tx = M + 2 * (w + gap) + w / 2
    f.arrow([(rx + 60, y1 + card_h(r)), (rx + 60, y1 + card_h(r) + 60), (tx, y1 + card_h(r) + 60), (tx, y2)], ROLE["focus"]["stroke"])
    px = M + w + gap + w / 2
    f.arrow([(M + 2 * (w + gap), y2 + 100), (px, y2 + 100), (px, y1 + card_h(p))], INK["muted_line"], dash="dashed")
    f.text(M, y2 + 200, "Free space is measured with df, never inferred from folder sizes. A flat result means a local snapshot still holds the space; Claude gives you the sudo line.",
           "footer", INK["secondary"])
    return f.els


FIGURES = {"browser-select": browser_select, "claude-usage": claude_usage,
           "session-export": session_export, "mac-disk-cleanup": mac_disk_cleanup}


def build(dy=0, step=1400):
    out = {}
    for n, (name, fn) in enumerate(FIGURES.items()):
        els = fn()
        for i, e in enumerate(els):
            e["id"] = f"rd-{name}-{i:03d}"
            e["y"] += dy + n * step
        out[name] = els
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", help="folder for <name>.excalidraw files")
    ap.add_argument("--post", action="store_true", help="add the figures to a live canvas")
    ap.add_argument("--canvas", default="http://127.0.0.1:3030")
    ap.add_argument("--dy", type=float, default=0, help="shift every figure down by N")
    a = ap.parse_args()
    figs = build(a.dy)
    if a.out:
        for name, els in figs.items():
            scene = dict(type="excalidraw", version=2, source="claude-skills/assets/diagrams/figures.py",
                         elements=els, appState=dict(viewBackgroundColor=ds.T["export"]["background"]), files={})
            pathlib.Path(a.out, f"{name}.excalidraw").write_text(json.dumps(scene, indent=1))
        print(f"wrote {len(figs)} figures to {a.out}")
    if a.post:
        for name, els in figs.items():
            req = urllib.request.Request(f"{a.canvas}/api/elements/batch", method="POST",
                                         data=json.dumps({"elements": els}).encode(),
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req) as r:
                print(f"{name}: posted {len(els)} elements, HTTP {r.status}")
    if not (a.out or a.post):
        ap.error("give --out and/or --post")


if __name__ == "__main__":
    main()
