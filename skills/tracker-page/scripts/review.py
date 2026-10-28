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
  The reference of a card is "<group name> / <card id>". Approved cards show an Approved label; the board counts
  approved / held / pending per group from this file, so the page never disagrees with what was approved.

Each card shows BEFORE (left, removed words red) and AFTER (right, added words green), full text on both sides;
an inline diff is behind a toggle. Unchanged cards are folded away at the bottom, with "Approve all unchanged".
Approve / Hold / Not reviewed and the note are saved in the browser; keys: j/k move, a approve, h hold,
u not reviewed, n note. "Copy summary for Claude" copies lines "<ref>: approve|hold|unreviewed — note" for the
human to paste back into the session.
"""
import difflib, html, json, pathlib, re, sys

THEME = (pathlib.Path(__file__).resolve().parent / 'theme.css').read_text()
CSS = '''
main{max-width:1500px}
.bar{position:sticky;top:0;z-index:1;background:var(--bg);border:1px solid var(--line);border-radius:6px;margin:16px 0;padding:8px 16px;display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center}
.bar .keys{margin-left:auto}
.card{scroll-margin-top:72px}.card.cur{box-shadow:0 0 0 2px var(--acc)}
.card.approve{border-color:color-mix(in srgb,var(--ok) 55%,var(--line))}.card.hold{border-color:color-mix(in srgb,var(--bad) 55%,var(--line))}
.seg{display:inline-flex;margin-left:auto}.seg label{font-size:12px;font-weight:500;padding:3px 12px;border:1px solid var(--line);background:var(--sub);cursor:pointer;white-space:nowrap}
.seg label:first-child{border-radius:6px 0 0 6px}.seg label:last-child{border-radius:0 6px 6px 0}.seg label+label{border-left:0}
.seg input{position:absolute;opacity:0;pointer-events:none}.seg label:has(input:focus-visible){outline:2px solid var(--acc)}
.seg label:has(input[value=approve]:checked){background:var(--ok-bg);color:var(--ok)}.seg label:has(input[value=hold]:checked){background:var(--bad-bg);color:var(--bad)}
.seg label:has(input[value=unreviewed]:checked){color:var(--fg)}
.l-approve{color:var(--ok)}.l-hold{color:var(--bad)}
.diff{display:grid;grid-template-columns:1fr 1fr}.diff>div{padding:10px 16px;white-space:pre-wrap;overflow-wrap:anywhere;font-size:13.5px}.diff>div+div{border-left:1px solid var(--line)}
.diff h3,.inl h3{margin:0 0 4px;font-size:12px;font-weight:600;color:var(--mute)}
.inl{display:none;padding:10px 16px;white-space:pre-wrap;overflow-wrap:anywhere;font-size:13.5px}body.inline .inl{display:block}body.inline .diff{display:none}
@media (max-width:800px){.diff{grid-template-columns:1fr}.diff>div+div{border-left:0;border-top:1px solid var(--line)}}
.ctx{white-space:pre-wrap;color:var(--mute);font-size:13px;max-height:10em;overflow:auto;margin:6px 0 0}
.box-f details{flex-basis:100%}.box-f summary{cursor:pointer;color:var(--mute);font-size:12px}
.box-f textarea{flex:1;min-width:200px}
details.unch>summary{cursor:pointer;margin:16px 0 8px}details.unch>summary .btn{margin-left:8px}
#sum{white-space:pre-wrap;font:12px ui-monospace,monospace;background:var(--sub);border:1px solid var(--line);border-radius:6px;padding:10px 12px}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:10px 16px;border-top:1px solid var(--line)}thead th{border-top:0;font-size:12px;color:var(--mute);font-weight:600}
td.num,th.num{text-align:right;width:80px}
'''
JS = r'''
const $=(q,e=document)=>e.querySelector(q),$$=(q,e=document)=>[...e.querySelectorAll(q)];
const K=document.body.dataset.key;let st={};try{st=JSON.parse(localStorage.getItem(K)||'{}')}catch(e){}
const save=()=>{try{localStorage.setItem(K,JSON.stringify(st))}catch(e){}};
const cards=$$('.card'),val=c=>(st[c.id]||{}).v||c.dataset.state||'unreviewed';
function paint(c){const v=val(c);c.classList.toggle('approve',v==='approve');c.classList.toggle('hold',v==='hold');
  const r=$(`input[value="${v}"]`,c);if(r)r.checked=true}
function progress(){const n=cards.filter(c=>val(c)!=='unreviewed').length;$('#done').textContent=`${n} of ${cards.length} reviewed`;
  $('#bar i').style.width=(cards.length?100*n/cards.length:0)+'%'}
function set(c,v){st[c.id]=st[c.id]||{};st[c.id].v=v;save();paint(c);progress()}
cards.forEach(c=>{const s=st[c.id]||{},t=$('textarea',c);if(s.n)t.value=s.n;paint(c);
  $$('input[type=radio]',c).forEach(r=>r.onchange=()=>set(c,r.value));
  t.oninput=()=>{st[c.id]=st[c.id]||{};st[c.id].n=t.value;save()}});
progress();
let cur=-1;function go(i){if(!cards.length)return;cur=Math.max(0,Math.min(cards.length-1,i));
  cards.forEach(c=>c.classList.remove('cur'));const c=cards[cur];const u=c.closest('details');if(u)u.open=true;
  c.classList.add('cur');c.scrollIntoView({block:'start',behavior:'smooth'})}
$('#next').onclick=()=>{const i=cards.findIndex((c,k)=>k>cur&&val(c)==='unreviewed'),j=i<0?cards.findIndex(c=>val(c)==='unreviewed'):i;if(j>=0)go(j)};
function toggleView(){const i=document.body.classList.toggle('inline');$('#view').textContent=i?'Side by side':'Inline diff';try{localStorage.setItem(K+'-view',i?'inline':'sbs')}catch(e){}}
$('#view').onclick=toggleView;try{if(localStorage.getItem(K+'-view')==='inline')toggleView()}catch(e){}
const all=$('#allunch');if(all)all.onclick=e=>{e.preventDefault();$$('.unch .card').forEach(c=>set(c,'approve'))};
$('#copy').onclick=async()=>{const L=cards.map(c=>{const s=st[c.id]||{};return c.dataset.ref+': '+val(c)+(s.n?' — '+s.n.replace(/\s*\n\s*/g,' '):'')});
  const p=$('#sum'),txt=L.join('\n');p.textContent=txt;p.hidden=false;
  try{await navigator.clipboard.writeText(txt);$('#copy').textContent='Copied ✓';setTimeout(()=>$('#copy').textContent='Copy summary for Claude',2000)}
  catch(e){$('#copy').textContent='Select the text below and copy it'}};
document.addEventListener('keydown',e=>{if(e.target.closest('textarea,input[type=text]')||e.metaKey||e.ctrlKey||e.altKey)return;
  const c=cards[cur];
  if(e.key==='j')go(cur+1);else if(e.key==='k')go(cur-1);
  else if(c&&e.key==='a')set(c,'approve');else if(c&&e.key==='h')set(c,'hold');else if(c&&e.key==='u')set(c,'unreviewed');
  else if(c&&e.key==='n'){e.preventDefault();$('textarea',c).focus()}else return;});
'''


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


def page(title, body, key=''):
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{title}</title><style>{THEME}{CSS}</style></head><body data-key="{key}"><main>{body}</main>'
            + (f'<script>{JS}</script>' if key else '') + '</body></html>')


def card(g, k, state):
    ref = f'{g} / {k["id"]}'; cid = slug(ref)
    L, R, I, add, rem = sbs(k.get('before', ''), k.get('after', ''))
    lab = {'approve': ('approve', 'Approved'), 'hold': ('hold', 'Held')}.get(state)  # recorded in approvals.json
    badge = f'<span class="label l-{lab[0]}" title="Recorded in approvals.json">{lab[1]}</span>' if lab else ''
    links = ' · '.join(f'<a href="{html.escape(u)}">{html.escape(l)}</a>' for l, u in (k.get('links') or {}).items())
    meta = f'{len(k.get("before", "").split())} → {len(k.get("after", "").split())} words · +{add} −{rem}' + (f' · {links}' if links else '')
    radios = ''.join(f'<label><input type="radio" name="{cid}" value="{v}">{t}</label>' for v, t in (('approve', 'Approve'), ('hold', 'Hold'), ('unreviewed', 'Not reviewed')))
    ctx = f'<details><summary>Requirement</summary><div class="ctx">{html.escape(k["context"])}</div></details>' if k.get('context') else ''
    return (f'<article class="box card" id="{cid}" data-ref="{html.escape(ref)}" data-state="{state}">'
            f'<div class="box-h">{html.escape(k.get("heading", k["id"]))} {badge}<span class="mute">{meta}</span>'
            f'<span class="seg" role="radiogroup" aria-label="Decision">{radios}</span></div>'
            f'<div class="diff"><div><h3>Before</h3>{L or "<i>(empty)</i>"}</div><div><h3>After</h3>{R or "<i>(empty)</i>"}</div></div><div class="inl"><h3>Changes</h3>{I}</div>'
            f'<div class="box-f">{ctx}<textarea rows="1" placeholder="Note (optional)" aria-label="Note on {html.escape(ref)}"></textarea></div></article>')


def build(cards_path, out, approvals_path=None):
    c = json.loads(pathlib.Path(cards_path).read_text()); out = pathlib.Path(out); out.mkdir(parents=True, exist_ok=True)
    ap = json.loads(pathlib.Path(approvals_path).read_text()) if approvals_path and pathlib.Path(approvals_path).exists() else {}
    ok, held = set(ap.get('approved', [])), set(ap.get('held', []))
    title = c.get('title', 'Review'); board = []
    for g in c['groups']:
        changed, same, n_ok, n_hold = [], [], 0, 0
        for k in g['cards']:
            ref = f'{g["name"]} / {k["id"]}'
            state = 'approve' if ref in ok else 'hold' if ref in held else ''
            n_ok += state == 'approve'; n_hold += state == 'hold'
            (changed if k.get('before', '') != k.get('after', '') else same).append(card(g['name'], k, state))
        unch = (f'<details class="unch"><summary>{len(same)} unchanged card{"s" if len(same) != 1 else ""} '
                f'<button class="btn" type="button" id="allunch">Approve all unchanged</button></summary>{"".join(same)}</details>') if same else ''
        bar = (f'<div class="bar"><b>{html.escape(g["name"])}</b><span id="done" class="mute"></span><span class="mini" id="bar"><i></i></span>'
               f'<button class="btn" type="button" id="next">Next unreviewed</button><button class="btn" type="button" id="view">Inline diff</button>'
               f'<button class="btn primary" type="button" id="copy">Copy summary for Claude</button>'
               f'<span class="keys small mute"><kbd>j</kbd> <kbd>k</kbd> move · <kbd>a</kbd> approve · <kbd>h</kbd> hold · <kbd>u</kbd> not reviewed · <kbd>n</kbd> note</span></div>')
        body = (f'<header class="head"><h1>{html.escape(title)}: {html.escape(g["name"])}</h1><nav><a href="index.html">All groups</a></nav>'
                f'<p class="mute">Before on the left, after on the right. Approve or Hold each card, add a note, then copy the summary into the session.</p></header>'
                f'{bar}<pre id="sum" hidden></pre>{"".join(changed)}{unch}')
        s = slug(g['name'])
        (out / f'{s}.html').write_text(page(html.escape(f'{title}: {g["name"]}'), body, f'rv-{slug(title)}-{s}'))
        board.append((s, g['name'], len(g['cards']), len(changed), n_ok, n_hold))
    rows, tot = [], [0, 0, 0]
    for s, name, t, ch, a, h in board:
        tot[0] += t; tot[1] += a; tot[2] += h; pct = round(100 * a / t) if t else 0
        lab, cls = ('Done', 'l-done') if a == t else ('Has holds', 'l-blocked') if h else ('In review', 'l-in-progress') if a else ('Not started', 'l-todo')
        rows.append(f'<tr><td><a href="{s}.html"><b>{html.escape(name)}</b></a><div class="small mute">{ch} of {t} changed</div></td><td class="num">{a}</td><td class="num">{h}</td>'
                    f'<td class="num">{t - a - h}</td><td><span class="mini" role="img" aria-label="{pct}% approved"><i style="width:{pct}%"></i></span> <span class="small mute">{pct}%</span></td>'
                    f'<td><span class="label {cls}">{lab}</span></td></tr>')
    tp = round(100 * tot[1] / tot[0]) if tot[0] else 0
    body = (f'<header class="head"><h1>{html.escape(title)}: status</h1>'
            f'<p class="mute">{tot[1]} of {tot[0]} approved ({tp}%) · {tot[2]} held · counts come from the approvals file, not the browser</p></header>'
            f'<div class="box" style="margin-top:16px"><table><thead><tr><th>Group</th><th class="num">Approved</th><th class="num">Held</th><th class="num">Pending</th><th>Progress</th><th>Status</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')
    (out / 'index.html').write_text(page(f'{html.escape(title)} status', body))
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
