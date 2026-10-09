#!/usr/bin/env python3
"""Side-by-side review pages + status board, driven by two JSON files.

usage:
  review.py build  <cards.json> <out_dir> [--approvals approvals.json]
  review.py record <approvals.json> <summary.txt>     ingest a pasted "Summary for Claude"

cards.json:
  {"title": "Cell review", "groups": [
     {"name": "Acme", "cards": [
        {"id": "DES-001", "heading": "DES-001 · Project scope",
         "context": "requirement / what to check (optional, collapsible)",
         "before": "old text", "after": "new text", "links": {"evidence": "url-or-path"}}]}]}

approvals.json:  {"approved": ["Acme / DES-001", ...], "held": ["Acme / DES-002"], "notes": {"Acme / DES-002": "..."}}
  The reference of a card is "<group name> / <card id>". Approved cards show a ✅ badge; the board counts
  approved / held / pending per group from this file, so the page never disagrees with what was approved.

Each card shows BEFORE (left, removed words red) and AFTER (right, added words green), full text on both sides;
an inline diff is behind a toggle. Approve / Hold / note are saved in the browser; "Summary for Claude" copies
lines "<ref>: approve|hold|unreviewed — note" for the human to paste back into the session.
"""
import difflib, html, json, pathlib, re, sys

THEME = (pathlib.Path(__file__).resolve().parent / 'tracker.py').read_text().split('THEME = """', 1)[1].split('"""', 1)[0]


def toks(s): return re.findall(r'\S+|\s+', s or '')


def sbs(a, b):
    ta, tb = toks(a), toks(b); L, R, I = [], [], []; add = rem = 0
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ta, tb, autojunk=False).get_opcodes():
        A, B = html.escape(''.join(ta[i1:i2])), html.escape(''.join(tb[j1:j2]))
        if op == 'equal': L.append(A); R.append(B); I.append(A); continue
        if A: L.append(f'<del>{A}</del>'); I.append(f'<del>{A}</del>'); rem += len(A.split())
        if B: R.append(f'<ins>{B}</ins>'); I.append(f'<ins>{B}</ins>'); add += len(B.split())
    return ''.join(L), ''.join(R), ''.join(I), add, rem


def slug(s): return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-') or 'group'


PAGE = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>{theme}
main{{max-width:1500px}}.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:14px 0}}
.card h2{{font-size:16px;margin:0 0 4px}}.badge{{font-size:12px;font-weight:500;margin-left:8px;padding:2px 8px;border-radius:999px;border:1px solid var(--line);color:var(--mute)}}
.badge.ok{{color:var(--ok);border-color:var(--ok)}}.badge.hold{{color:var(--q);border-color:var(--q)}}.card.approve{{border-color:var(--ok)}}.card.hold{{border-color:var(--q)}}
.meta{{font-size:12px;color:var(--mute)}}.ctx{{font-size:13px;color:var(--mute);white-space:pre-wrap;max-height:8em;overflow:auto;border-left:3px solid var(--line);padding-left:8px;margin:6px 0}}
.sbs{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:8px}}.sbs>div{{border:1px solid var(--line);border-radius:8px;padding:8px 10px;background:var(--bg);white-space:pre-wrap;font-size:13.5px;overflow-wrap:anywhere}}
.sbs h3{{margin:0 0 6px;font-size:12px;color:var(--mute);font-weight:600;text-transform:uppercase;letter-spacing:.04em}}@media (max-width:800px){{.sbs{{grid-template-columns:1fr}}}}
.inl{{white-space:pre-wrap;font-size:14px;overflow-wrap:anywhere;display:none}}body.inline .inl{{display:block}}body.inline .sbs{{display:none}}
ins{{background:var(--ins);text-decoration:none}}del{{background:var(--del)}}button{{font:inherit;padding:4px 12px;border-radius:8px;border:1px solid var(--line);background:var(--bg);color:var(--ink);cursor:pointer}}
.ctl{{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}}textarea{{width:100%;font:inherit;margin-top:6px;background:var(--bg);color:var(--ink);border:1px solid var(--line);border-radius:8px}}
details summary{{cursor:pointer;color:var(--mute);font-size:13px}}#sum{{white-space:pre-wrap;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px}}</style></head>
<body><main><h1>{title}</h1><p class="sub">Before on the left, after on the right. Approve or Hold each card, add a note, then copy <b>Summary for Claude</b> into the session. <a href="index.html">All groups</a></p>
<p><button onclick="summary()">Summary for Claude</button> <button onclick="toggleView()" id="vbtn">Switch to inline diff</button></p><pre id="sum" hidden></pre>
{cards}</main><script>
const K='{key}';let st={{}};try{{st=JSON.parse(localStorage.getItem(K)||'{{}}')}}catch(e){{}}
function save(){{try{{localStorage.setItem(K,JSON.stringify(st))}}catch(e){{}}}}
function set(id,v){{st[id]=st[id]||{{}};st[id].v=v;document.getElementById(id).className='card '+v;save()}}
function note(id,t){{st[id]=st[id]||{{}};st[id].n=t;save()}}
for(const [id,s] of Object.entries(st)){{const e=document.getElementById(id);if(e){{if(s.v)e.className='card '+s.v;if(s.n)e.querySelector('textarea').value=s.n}}}}
function toggleView(){{const i=document.body.classList.toggle('inline');document.getElementById('vbtn').textContent=i?'Switch to side by side':'Switch to inline diff';try{{localStorage.setItem(K+'-view',i?'inline':'sbs')}}catch(e){{}}}}
try{{if(localStorage.getItem(K+'-view')==='inline')toggleView()}}catch(e){{}}
function summary(){{const L=[];document.querySelectorAll('.card').forEach(c=>{{const s=st[c.id]||{{}};L.push(c.dataset.ref+': '+(s.v||c.dataset.state||'unreviewed')+(s.n?' — '+s.n:''))}});const p=document.getElementById('sum');p.textContent=L.join('\\n');p.hidden=false;navigator.clipboard&&navigator.clipboard.writeText(p.textContent)}}
</script></body></html>'''


def build(cards_path, out, approvals_path=None):
    c = json.loads(pathlib.Path(cards_path).read_text()); out = pathlib.Path(out); out.mkdir(parents=True, exist_ok=True)
    ap = json.loads(pathlib.Path(approvals_path).read_text()) if approvals_path and pathlib.Path(approvals_path).exists() else {}
    ok, held = set(ap.get('approved', [])), set(ap.get('held', []))
    board = []
    for g in c['groups']:
        cards, n_ok, n_hold, changed = [], 0, 0, 0
        for k in g['cards']:
            ref = f'{g["name"]} / {k["id"]}'; cid = slug(ref)
            L, R, I, add, rem = sbs(k.get('before', ''), k.get('after', ''))
            changed += k.get('before', '') != k.get('after', '')
            state = 'approve' if ref in ok else 'hold' if ref in held else ''
            n_ok += state == 'approve'; n_hold += state == 'hold'
            badge = {'approve': '<span class="badge ok">✅ Approved</span>', 'hold': '<span class="badge hold">⏸ Held</span>'}.get(state, '<span class="badge">· Pending</span>')
            links = ' · '.join(f'<a href="{html.escape(u)}">{html.escape(l)}</a>' for l, u in (k.get('links') or {}).items())
            ctx = f'<details><summary>Context</summary><div class="ctx">{html.escape(k["context"])}</div></details>' if k.get('context') else ''
            cards.append(f'<div class="card {state}" id="{cid}" data-ref="{html.escape(ref)}" data-state="{state}"><h2>{html.escape(k.get("heading", k["id"]))} {badge}</h2>'
                         f'<div class="meta">{len(k.get("before","").split())} → {len(k.get("after","").split())} words · +{add} / −{rem}{" · unchanged" if not add and not rem else ""}{" · " + links if links else ""}</div>{ctx}'
                         f'<div class="sbs"><div><h3>Before</h3>{L or "<i>(empty)</i>"}</div><div><h3>After</h3>{R}</div></div><div class="inl">{I}</div>'
                         f'<div class="ctl"><button onclick="set(\'{cid}\',\'approve\')">Approve</button><button onclick="set(\'{cid}\',\'hold\')">Hold</button></div>'
                         f'<textarea rows="2" placeholder="Note" oninput="note(\'{cid}\',this.value)"></textarea></div>')
        s = slug(g['name'])
        (out / f'{s}.html').write_text(PAGE.format(title=html.escape(f'{c.get("title","Review")}: {g["name"]}'), theme=THEME, cards=''.join(cards), key=f'rv-{slug(c.get("title","review"))}-{s}'))
        board.append((s, g['name'], len(g['cards']), changed, n_ok, n_hold))
    rows, tot = [], [0, 0, 0]
    for s, name, t, ch, a, h in board:
        tot[0] += t; tot[1] += a; tot[2] += h; pct = round(100 * a / t) if t else 0
        lab, cls = ('✅ Done', 'done') if a == t else ('⏸ Has holds', 'hold') if h else ('⏳ In review', 'prog') if a else ('· Not started', 'todo')
        rows.append(f'<tr class="{cls}"><td><a href="{s}.html"><b>{html.escape(name)}</b></a><div class="m">{ch} of {t} changed</div></td><td class="num">{a}</td><td class="num">{h}</td>'
                    f'<td class="num">{t-a-h}</td><td><div class="bar"><i style="width:{pct}%"></i></div><div class="m">{pct}%</div></td><td class="st">{lab}</td></tr>')
    tp = round(100 * tot[1] / tot[0]) if tot[0] else 0
    (out / 'index.html').write_text(f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(c.get("title","Review"))} Status</title>
<style>{THEME}.wrap{{overflow-x:auto}}table{{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}}th,td{{padding:10px 12px;border-bottom:1px solid var(--line);text-align:left}}
th{{font-size:12px;color:var(--mute)}}td.num{{text-align:right;width:70px}}.m{{font-size:12px;color:var(--mute)}}.bar{{height:8px;background:var(--line);border-radius:4px;overflow:hidden;min-width:120px}}.bar i{{display:block;height:100%;background:var(--ok)}}
tr.done td.st{{color:var(--ok)}}tr.hold td.st{{color:var(--q)}}tr.prog td.st{{color:var(--warn)}}tr.todo td.st{{color:var(--mute)}}</style></head>
<body><main><h1>{html.escape(c.get("title","Review"))}: status</h1><p class="sub">{tot[1]} of {tot[0]} approved ({tp}%) · {tot[2]} held · source: approvals file</p>
<div class="wrap"><table><thead><tr><th>Group</th><th class="num">Approved</th><th class="num">Held</th><th class="num">Pending</th><th>Progress</th><th>Status</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div></main></body></html>''')
    print(f'{out}/index.html: {tot[1]}/{tot[0]} approved, {tot[2]} held')


def record(approvals_path, summary_path):
    p = pathlib.Path(approvals_path); ap = json.loads(p.read_text()) if p.exists() else {}
    ok, held, notes = set(ap.get('approved', [])), set(ap.get('held', [])), ap.get('notes', {})
    for line in pathlib.Path(summary_path).read_text().splitlines():
        m = re.match(r'^(.+?):\s*(approve|approved|hold|held|unreviewed)\s*(?:—\s*(.*))?$', line.strip())
        if not m: continue
        ref, v, n = m.group(1).strip(), m.group(2), (m.group(3) or '').strip()
        ok.discard(ref); held.discard(ref)
        if v.startswith('approve'): ok.add(ref)
        elif v.startswith('hold'): held.add(ref)
        if n: notes[ref] = n
    p.write_text(json.dumps({'approved': sorted(ok), 'held': sorted(held), 'notes': notes}, indent=1, ensure_ascii=False))
    print(f'{p}: {len(ok)} approved, {len(held)} held')


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[:1] == ['build'] and len(a) >= 3:
        build(a[1], a[2], a[a.index('--approvals') + 1] if '--approvals' in a else None)
    elif a[:1] == ['record'] and len(a) == 3:
        record(a[1], a[2])
    else:
        sys.exit(__doc__)
