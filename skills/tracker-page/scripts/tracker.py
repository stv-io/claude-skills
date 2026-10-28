#!/usr/bin/env python3
"""Live task tracker: one status.json drives a local HTML page (index.html) that a human keeps open.

usage:
  tracker.py init  <dir> --title "Final review" [--subtitle "..."]
  tracker.py item  <dir> <id> [--title T] [--phase P] [--status S] [--note N] [--rev R] [--link LABEL=URL ...]
  tracker.py link  <dir> LABEL=URL [...]          top-of-page links (reports, sheets, PRs)
  tracker.py block <dir> "text" | --clear         blockers panel (red)
  tracker.py ask   <dir> "text" | --clear         decisions-for-the-human panel (amber)
  tracker.py log   <dir> "text"                   append a timestamped line to <dir>/LOG.md (append-only)
  tracker.py feedback <dir> [--all]               list the human's comments (open ones only by default)
  tracker.py feedback <dir> --wait [--timeout S]  block until the human presses "Send to Claude", print what was sent
  tracker.py feedback <dir> --resolve ID [--reply "what was done"]
  tracker.py render <dir>                         rebuild <dir>/index.html (every other command also renders)
  tracker.py serve <dir> [--port 8765] [--no-mdserve]
                                                  serve <dir> on http://localhost:<port> (foreground)

Statuses: todo, in-progress, review, decision, blocked, done.
Notes, links and log lines are linkified: http(s) URLs, and relative paths to files in <dir> (e.g. reports/x.md).
Times are UTC. While served, the page checks for changes every 15 s and reloads only when something changed
and no comment is being written; opened as a file, it reloads every 30 s.

Comments: each item has a Comment button, and the sidebar takes general comments. `serve` saves each one to
<dir>/feedback.json as soon as it is written (append-only; resolving adds a reply, never deletes). "Send to Claude"
marks the saved comments as sent, which ends a `feedback --wait` running in the agent's session. If the page can't
save (opened as a file, an older server, or no server), it says why and copies the comment to the clipboard.

Markdown links (relative *.md, including ../ paths elsewhere in the repo) open formatted: the page links
them as /md?p=<path>, and `serve` starts one `mdserve` per folder on demand (mdserve only serves a flat
folder) and redirects there. Targets must sit inside the git repo that holds <dir>. Without mdserve on
PATH, or with --no-mdserve, the file is served as plain text.
"""
import argparse, contextlib, datetime, fcntl, hashlib, html, json, os, pathlib, re, sys, http.server
import atexit, shutil, signal, socket, subprocess, tempfile, threading, time, urllib.parse

STATUS = {  # label, counts as "needs you"
    'done': ('Done', False), 'review': ('Ready for review', True), 'in-progress': ('In progress', False),
    'decision': ('Needs a decision', True), 'blocked': ('Blocked', True), 'todo': ('Not started', False),
}
COLOUR = {'done': 'var(--ok)', 'in-progress': 'var(--warn)', 'review': 'var(--acc)', 'decision': 'var(--bad)', 'blocked': 'var(--bad)', 'todo': 'transparent'}
THEME = (pathlib.Path(__file__).resolve().parent / 'theme.css').read_text()
ICONS = '''<svg width="0" height="0" style="position:absolute" aria-hidden="true">
<symbol id="i-done" viewBox="0 0 16 16"><circle cx="8" cy="8" r="7" fill="var(--ok)"/><path d="M4.8 8.2l2 2 4.4-4.4" stroke="#fff" stroke-width="1.6" fill="none"/></symbol>
<symbol id="i-in-progress" viewBox="0 0 16 16"><circle cx="8" cy="8" r="6.25" stroke="var(--warn)" stroke-width="1.5" fill="none"/><path d="M8 3.5a4.5 4.5 0 010 9z" fill="var(--warn)"/></symbol>
<symbol id="i-review" viewBox="0 0 16 16"><circle cx="8" cy="8" r="6.25" stroke="var(--acc)" stroke-width="1.5" fill="none"/><circle cx="8" cy="8" r="2" fill="var(--acc)"/></symbol>
<symbol id="i-decision" viewBox="0 0 16 16"><circle cx="8" cy="8" r="6.25" stroke="var(--bad)" stroke-width="1.5" fill="none"/><path d="M6.3 6.3a1.8 1.8 0 113 1.3c-.7.5-1.3.8-1.3 1.7" stroke="var(--bad)" stroke-width="1.4" fill="none"/><circle cx="8" cy="11.4" r=".8" fill="var(--bad)"/></symbol>
<symbol id="i-blocked" viewBox="0 0 16 16"><circle cx="8" cy="8" r="6.25" stroke="var(--bad)" stroke-width="1.5" fill="none"/><path d="M5 8h6" stroke="var(--bad)" stroke-width="1.6"/></symbol>
<symbol id="i-todo" viewBox="0 0 16 16"><circle cx="8" cy="8" r="6.25" stroke="var(--todo)" stroke-width="1.5" fill="none" stroke-dasharray="2.2 2"/></symbol>
</svg>'''
CSS = '''
.cols{display:grid;grid-template-columns:minmax(0,1fr) 280px;gap:24px}@media(max-width:860px){.cols{grid-template-columns:1fr}}
details.box>summary{list-style:none;cursor:pointer}details.box>summary::-webkit-details-marker{display:none}
details.box:not([open])>summary{border-bottom:0;border-radius:6px}
details.box>summary:before{content:"▸";color:var(--mute);font-size:11px;transition:transform .15s}details.box[open]>summary:before{transform:rotate(90deg)}
.row{display:grid;grid-template-columns:20px 28px minmax(0,1fr) auto auto;gap:0 10px;align-items:start;padding:10px 16px;border-top:1px solid var(--line)}
.box>summary+.row,.box>.row:first-child{border-top:0}.row:hover{background:color-mix(in srgb,var(--sub) 70%,transparent)}
.row .t{font-weight:600;overflow-wrap:anywhere}.row.done .t{font-weight:400;color:var(--mute)}
.row .meta{display:flex;gap:8px;align-items:center}
.row .sub{grid-column:3/-1;color:var(--mute);font-size:12px;overflow-wrap:anywhere}
.ico{width:16px;height:16px;margin-top:2px}
.cmt{grid-column:3/-1;margin-top:8px;border:1px solid var(--line);border-radius:6px;overflow:hidden;font-size:13px}
.cmt .ch{background:var(--sub);padding:3px 10px;font-size:12px;color:var(--mute);border-bottom:1px solid var(--line)}
.cmt p{margin:0;padding:6px 10px;white-space:pre-wrap}.cmt .re{border-top:1px dashed var(--line);color:var(--mute)}
.cmt.resolved{opacity:.75}
.compose{grid-column:3/-1;margin-top:8px}.compose .acts{display:flex;justify-content:flex-end;align-items:center;gap:8px;margin-top:8px}
.compose .msg{margin-right:auto}
aside .side{position:sticky;top:16px}
.tl{list-style:none;margin:0 0 6px;padding:0 0 0 14px;border-left:2px solid var(--line)}
.tl li{position:relative;padding:0 0 12px 12px;overflow-wrap:anywhere}.tl li:before{content:"";position:absolute;left:-20px;top:5px;width:10px;height:10px;border-radius:50%;background:var(--bg);border:2px solid var(--line)}
.tl time{display:block;font-size:12px;color:var(--mute)}
#gen .cmt,#gen .compose{margin:8px 0 0}#gen>.btn{margin-top:8px}
.live:before{content:"";display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--ok);margin-right:6px}.live.off:before{background:var(--bad)}
'''
JS = r'''
const $=(q,e=document)=>e.querySelector(q),$$=(q,e=document)=>[...e.querySelectorAll(q)];
const TABS=['all','needs','open','done','feedback'];
function filter(){const h=location.hash.slice(1),f=TABS.includes(h)?h:'all';
  $$('.tabs a').forEach(a=>a.setAttribute('aria-current',a.hash==='#'+f));
  $$('.row').forEach(r=>r.hidden=f!=='all'&&!r.dataset.f.split(' ').includes(f));
  $$('.box').forEach(b=>{const rows=$$('.row',b);b.hidden=rows.length>0&&rows.every(r=>r.hidden);if(f!=='all'&&!b.hidden)b.open=true})}
addEventListener('hashchange',filter);filter();
$$('.tabs a').forEach(a=>a.onclick=e=>{e.preventDefault();history.replaceState(null,'',a.hash);filter()});
function keep(){sessionStorage.setItem('tracker-y',scrollY)}
async function post(path,body){  // -> [error message or '', true when the page can't save at all]
  if(location.protocol==='file:')return ['Not saved: this page was opened as a file, not through tracker.py serve.',true];
  let r;try{r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})}
  catch(e){return ['Not saved: the tracker server is not responding.',true]}
  if(r.ok)return ['',false];
  if([404,405,501].includes(r.status))return ['Not saved: this tracker server is running an older tracker.py. Restart tracker.py serve to save comments.',true];
  return ['Not saved: '+await r.text(),false]}
const send=$('#send');if(send)send.onclick=async()=>{send.disabled=true;const [err]=await post('/feedback/send',{});
  if(!err){keep();return location.reload()}send.disabled=false;$('#sendmsg').textContent=err};
const y=sessionStorage.getItem('tracker-y');if(y!==null){sessionStorage.removeItem('tracker-y');scrollTo(0,+y)}
function compose(row){
  if($('.compose',row))return $('.compose textarea',row).focus();
  const item=row.dataset.item||null,f=document.createElement('div');f.className='compose';
  f.innerHTML='<textarea rows="3"></textarea><div class="acts"><span class="msg small mute" role="status"></span>'+
    '<button class="btn" type="button">Cancel</button><button class="btn primary" type="button">Save comment</button></div>';
  row.append(f);const t=$('textarea',f),[no,ok]=$$('button',f),msg=$('.msg',f);
  t.setAttribute('aria-label',item?'Comment on item '+item:'General comment');t.focus();
  no.onclick=()=>f.remove();
  ok.onclick=async()=>{const text=t.value.trim();if(!text)return t.focus();ok.disabled=true;
    const [err,cantSave]=await post('/feedback',{item,text});if(!err){keep();return location.reload()}
    ok.disabled=false;if(!cantSave){msg.textContent=err;return}
    try{await navigator.clipboard.writeText((item?'Comment on item '+item+': ':'Comment: ')+text);msg.textContent=err+' Copied to the clipboard instead; paste it into the session.'}
    catch(_){msg.textContent=err+' Copy your text and paste it into the session.'}};
  t.onkeydown=e=>{if(e.key==='Enter'&&(e.metaKey||e.ctrlKey))ok.click();if(e.key==='Escape')f.remove()}}
document.addEventListener('click',e=>{const b=e.target.closest('[data-comment]');if(b)compose(b.closest('[data-item]'))});
const rev=$('meta[name=tracker-rev]').content,live=$('.live');
if(location.protocol==='file:')setInterval(()=>{if(!$('.compose')){keep();location.reload()}},30000);
else setInterval(async()=>{if($('.compose'))return;
  try{const t=await(await fetch(location.pathname,{cache:'no-store'})).text(),m=t.match(/name="tracker-rev" content="(\w+)"/);
    live.classList.remove('off');live.textContent='Live';if(m&&m[1]!==rev){keep();location.reload()}}
  catch(e){live.classList.add('off');live.textContent='Server not responding'}},15000);
'''


def now(): return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
def path(d): return pathlib.Path(d) / 'status.json'
def short(ts):
    """'2026-10-28 11:47 UTC' -> '11:47 UTC' when it is today (UTC); other dates stay in full."""
    return ts[11:] if ts[:10] == now()[:10] else ts
def write(p, text):
    """Write via a temp file and rename, so the server never reads a half-written file."""
    p = pathlib.Path(p); tmp = p.with_name(f'.{p.name}.{os.getpid()}.tmp'); tmp.write_text(text); os.replace(tmp, p)
def load(d):
    p = path(d)
    if not p.exists(): sys.exit(f'{p} not found — run: tracker.py init {d} --title ...')
    return json.loads(p.read_text())
def save(d, s):
    s['updated'] = now(); write(path(d), json.dumps(s, indent=1, ensure_ascii=False)); render(d, s)
def load_fb(d):
    p = pathlib.Path(d) / 'feedback.json'
    return json.loads(p.read_text()).get('comments', []) if p.exists() else []
@contextlib.contextmanager
def fb_lock(d):
    """Serialise read-modify-write of feedback.json between the server and CLI processes."""
    key = hashlib.sha1(str(pathlib.Path(d).resolve()).encode()).hexdigest()[:16]  # kept out of the tracker folder (and git)
    with open(pathlib.Path(tempfile.gettempdir()) / f'tracker-feedback-{key}.lock', 'w') as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try: yield
        finally: fcntl.flock(fh, fcntl.LOCK_UN)
def save_fb(d, comments): write(pathlib.Path(d) / 'feedback.json', json.dumps({'comments': comments}, indent=1, ensure_ascii=False))


def mdlink(u):
    """Route relative markdown links through the server's /md endpoint (rendered by mdserve)."""
    if re.match(r'^[a-z][\w+.-]*:|^[#/]', u): return u
    p, _, frag = u.partition('#')
    return f'/md?p={urllib.parse.quote(p)}' + (f'#{frag}' if frag else '') if p.endswith('.md') else u


def linkify(text, d):
    t = html.escape(text)
    t = re.sub(r'(https?://[^\s<)]+)', r'<a href="\1">\1</a>', t)
    def rel(m):
        p = m.group(0)
        return f'<a href="{mdlink(p)}">{p}</a>' if (pathlib.Path(d) / html.unescape(p)).exists() else p
    return re.sub(r'(?<![\w/">])(?:[\w.-]+/)*[\w.-]+\.(?:md|html|json|csv|pdf|xlsx|txt|png|jpg)\b', rel, t)


def links(pairs, sep=' · '): return sep.join(f'<a href="{html.escape(mdlink(u))}">{html.escape(l)}</a>' for l, u in (pairs or {}).items())


def log_lines(d, n=6):
    """Last n LOG.md entries, newest first, as (time, text). Times are shown as written."""
    p = pathlib.Path(d) / 'LOG.md'
    if not p.exists(): return []
    rows = [m.groups() for m in (re.match(r'^- (\d{4}-\d\d-\d\d \d\d:\d\d(?: UTC)?) (.*)$', l) for l in p.read_text().splitlines()) if m]
    return rows[::-1][:n]


def stage(c):
    if c.get('state') == 'resolved': return 'resolved'
    return 'seen by Claude' if c.get('delivered_at') else 'sent to Claude' if c.get('sent_at') else 'saved, not sent yet'


def comment_html(c, d):
    who = f'You commented at {html.escape(short(c.get("at", "")))} · {stage(c)}'
    reply = f'<p class="re">↳ {linkify(c["reply"], d)}</p>' if c.get('reply') else ''
    return f'<div class="cmt {html.escape(c.get("state", "open"))}" id="c{c["id"]}"><div class="ch">#{c["id"]} · {who}</div><p>{html.escape(c["text"])}</p>{reply}</div>'


def render(d, s=None, quiet=False):
    s = s or load(d); items = s.get('items', []); fb = load_fb(d)
    counts = {k: sum(i['status'] == k for i in items) for k in STATUS}
    pct = round(100 * counts['done'] / len(items)) if items else 0
    needs = sum(v for k, v in counts.items() if STATUS[k][1])
    open_fb = [c for c in fb if c.get('state') != 'resolved']; unsent = sum(not c.get('sent_at') for c in open_fb)
    by_item = {}
    for c in fb: by_item.setdefault(None if c.get('item') is None else str(c['item']), []).append(c)
    phases = {}
    for i in items: phases.setdefault(i.get('phase') or '', []).append(i)

    boxes = []
    for phase, grp in phases.items():
        rows = []
        for i in grp:
            st = i['status']; lab = STATUS.get(st, (st, False))[0]; iid = str(i['id'])
            cm = by_item.get(iid, [])
            f = ['open'] if st != 'done' else ['done']
            if STATUS.get(st, ('', False))[1]: f.append('needs')
            if any(c.get('state') != 'resolved' for c in cm): f.append('feedback')
            rev = f'<code>{html.escape(i["rev"])}</code>' if i.get('rev') else ''
            sub = ' · '.join(x for x in (linkify(i['note'], d) if i.get('note') else '', links(i.get('links'))) if x)
            rows.append(f'<div class="row {html.escape(st)}" id="i{html.escape(iid)}" data-item="{html.escape(iid)}" data-f="{" ".join(f)}">'
                        f'<svg class="ico" role="img" aria-label="{lab}"><use href="#i-{html.escape(st)}"/></svg><span class="mute">{html.escape(iid)}</span>'
                        f'<span class="t">{html.escape(i.get("title", ""))}</span><span class="meta">{rev}<span class="label l-{html.escape(st)}">{lab}</span></span>'
                        f'<button class="btn" type="button" data-comment>Comment</button>'
                        + (f'<div class="sub">{sub}</div>' if sub else '') + ''.join(comment_html(c, d) for c in cm) + '</div>')
        done = sum(x['status'] == 'done' for x in grp)
        head = (f'<summary class="box-h">{html.escape(phase)} <span class="mute">{done} of {len(grp)}</span>'
                f'<span class="mini end" role="img" aria-label="{done} of {len(grp)} done"><i style="width:{round(100 * done / len(grp))}%"></i></span></summary>') if phase else ''
        tag = 'details' if phase else 'section'
        boxes.append(f'<{tag} class="box"{" open" if phase and done < len(grp) else ""}>{head}{"".join(rows)}</{tag}>')

    seg = ''.join(f'<span style="flex:{v};background:{COLOUR[k]}"></span>' for k, v in counts.items() if v)
    legend = ''.join(f'<li style="--c:{COLOUR[k] if k != "todo" else "var(--line)"}">{v} {STATUS[k][0].lower()}{f" ({pct}%)" if k == "done" else ""}</li>' for k, v in counts.items() if v)
    def flash(key, cls, head):
        xs = [linkify(x, d) for x in s.get(key, [])]
        if not xs: return ''
        return f'<div class="flash {cls}"><b>{head}</b>' + (f'<span>{xs[0]}</span>' if len(xs) == 1 else '<ul>' + ''.join(f'<li>{x}</li>' for x in xs) + '</ul>') + '</div>'
    has_log = (pathlib.Path(d) / 'LOG.md').exists()
    top = links(s.get('links'), '') + (f'<a href="{mdlink("LOG.md")}">Run log</a>' if has_log else '')
    tab = lambda key, name, n: f'<a href="#{key}">{name} <span class="count">{n}</span></a>'
    activity = ''.join(f'<li><time>{html.escape(short(t))}</time>{linkify(x, d)}</li>' for t, x in log_lines(d))
    general = ''.join(comment_html(c, d) for c in by_item.get(None, []))
    timeline = (f'<ol class="tl">{activity}</ol><a class="small" href="{mdlink("LOG.md")}">Full log →</a>' if activity
                else '<p class="mute small">Nothing logged yet.</p>')
    sub = (linkify(s['subtitle'], d) + ' · ') if s.get('subtitle') else ''
    status = ', '.join(f'{v} {STATUS[k][0].lower()}' for k, v in counts.items() if v) or 'no items'
    content = ''.join(boxes) or '<p class="mute">No items yet.</p>'
    send_btn = (f'<p><button class="btn primary" type="button" id="send">Send {unsent} comment{"s" if unsent != 1 else ""} to Claude</button>'
                '<span id="sendmsg" class="small" role="status"></span></p>') if unsent else ''
    title = html.escape(s.get('title', 'Tracker'))
    body = f'''{ICONS}<main>
<header class="head"><h1>{title}</h1><nav aria-label="Related">{top}</nav>
<p class="mute">{sub}Updated {html.escape(s.get("updated", ""))} · <span class="live">Live</span></p></header>
<div class="prog" role="img" aria-label="{status}">{seg}</div>
<ul class="legend">{legend or "<li>No items yet</li>"}</ul>
<div style="margin-top:16px">{flash("blockers", "bad", "Blocked")}{flash("decisions", "warn", "Your decision")}</div>
<nav class="tabs" aria-label="Filter items">{tab("all", "All", len(items))}{tab("needs", "Needs you", needs)}{tab("open", "Open", len(items) - counts["done"])}{tab("done", "Done", counts["done"])}{tab("feedback", "Comments", len(open_fb))}</nav>
<div class="cols"><div>{content}</div>
<aside><div class="side"><h2 style="margin-top:0">Recent activity</h2>{timeline}
<h2>Comments</h2><p class="small mute" style="margin-top:0">{len(open_fb)} open. Each one is saved to <code>feedback.json</code> as you write it; <b>Send to Claude</b> tells a waiting session to read them.</p>
{send_btn}<div id="gen" data-item="">{general}<button class="btn" type="button" data-comment>General comment</button></div></div></aside></div>
<footer>Generated from <code>status.json</code> by <code>tracker.py</code>. Don't edit this page by hand.</footer></main>'''
    rev = hashlib.sha1(body.encode()).hexdigest()[:12]
    page = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta name="tracker-rev" content="{rev}"><noscript><meta http-equiv="refresh" content="30"></noscript>'
            f'<title>{f"({needs}) " if needs else ""}{title}</title><style>{THEME}{CSS}</style></head><body>{body}<script>{JS}</script></body></html>')
    write(pathlib.Path(d) / 'index.html', page)
    summary = ' · '.join(f'{v} {STATUS[k][0].lower()}' for k, v in counts.items() if v)
    if not quiet: print(f'index.html: {summary or "no items"}' + (f' · {len(open_fb)} open comment(s)' if open_fb else ''))


def add_comment(d, item, text):
    """Append one comment from the page. Returns its id. Raises ValueError on bad input."""
    if not isinstance(text, str) or not text.strip(): raise ValueError('empty comment')
    if len(text) > 10000: raise ValueError('comment too long')
    if item is not None:
        item = str(item)
        if item not in {str(i['id']) for i in load(d).get('items', [])}: raise ValueError(f'no item {item}')
    with fb_lock(d):
        fb = load_fb(d); cid = max((c['id'] for c in fb), default=0) + 1
        fb.append({'id': cid, 'item': item, 'text': text.strip(), 'at': now(), 'state': 'open'})
        save_fb(d, fb)
    return cid


def send_comments(d):
    """'Send to Claude': stamp every open, unsent comment with sent_at. Returns how many."""
    with fb_lock(d):
        fb = load_fb(d); t = now(); todo = [c for c in fb if c.get('state') != 'resolved' and not c.get('sent_at')]
        for c in todo: c['sent_at'] = t
        if todo: save_fb(d, fb)
    return len(todo)


def take_sent(d):
    """Open comments that were sent but not yet handed to the agent; stamps them delivered_at."""
    with fb_lock(d):
        fb = load_fb(d); new = [c for c in fb if c.get('state') != 'resolved' and c.get('sent_at') and not c.get('delivered_at')]
        t = now()
        for c in new: c['delivered_at'] = t
        if new: save_fb(d, fb)
    return new


def wait_sent(d, timeout=None, every=2.0):
    """Block until the human presses Send to Claude (or timeout seconds pass). Returns the sent comments."""
    end = None if timeout is None else time.monotonic() + timeout
    while True:
        new = take_sent(d)
        if new: render(d, quiet=True); return new
        if end is not None and time.monotonic() >= end: return []
        time.sleep(every)


class MdServers:
    """One mdserve per folder, started on first use and stopped when the tracker server exits."""
    def __init__(self):
        self.exe, self.procs, self.lock = shutil.which('mdserve'), {}, threading.Lock()
        atexit.register(self.stop)

    def url(self, f):
        if not self.exe: return None
        with self.lock:
            port, proc = self.procs.get(f.parent, (None, None))
            if proc is None or proc.poll() is not None:
                with socket.socket() as so: so.bind(('127.0.0.1', 0)); port = so.getsockname()[1]
                proc = subprocess.Popen([self.exe, '-p', str(port), str(f.parent)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.procs[f.parent] = (port, proc)
                for _ in range(50):  # up to 5 s for the listener
                    try: socket.create_connection(('127.0.0.1', port), 0.1).close(); break
                    except OSError: time.sleep(0.1)
        return f'http://127.0.0.1:{port}/{urllib.parse.quote(f.name)}'

    def stop(self):
        for _, proc in self.procs.values(): proc.terminate()


def handler(d, md):
    base = pathlib.Path(d).resolve(); lock = threading.Lock()
    top = subprocess.run(['git', '-C', str(base), 'rev-parse', '--show-toplevel'], capture_output=True, text=True)
    root = pathlib.Path(top.stdout.strip()).resolve() if top.returncode == 0 else base

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k): super().__init__(*a, directory=d, **k)
        def log_message(self, *a): pass
        def end_headers(self):
            self.send_header('Cache-Control', 'no-store'); super().end_headers()
        def reply(self, code, body, ctype='text/plain; charset=utf-8'):
            body = body.encode(); self.send_response(code); self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
        def do_GET(self):
            u = urllib.parse.urlsplit(self.path)
            # Files change several times a second; a 304 from the 1-second If-Modified-Since check would show a stale page.
            del self.headers['If-Modified-Since']
            if u.path != '/md': return super().do_GET()
            rel = urllib.parse.parse_qs(u.query).get('p', [''])[0]
            f = (base / rel).resolve()
            if not (f.is_file() and f.suffix == '.md' and f.is_relative_to(root)): return self.send_error(404, f'not a markdown file under {root}: {rel}')
            target = md.url(f) if md else None
            if target:
                self.send_response(302); self.send_header('Location', target); self.end_headers(); return
            body = f.read_bytes()
            self.send_response(200); self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
        def do_POST(self):
            route = urllib.parse.urlsplit(self.path).path
            if route not in ('/feedback', '/feedback/send'): return self.send_error(404)
            # JSON-only plus a same-origin check: a web page elsewhere can't post comments into the tracker.
            if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json': return self.reply(415, 'expected application/json')
            origin = self.headers.get('Origin')
            if origin and urllib.parse.urlsplit(origin).netloc != self.headers.get('Host'): return self.reply(403, 'cross-origin request refused')
            n = int(self.headers.get('Content-Length') or 0)
            if not 0 < n <= 20000: return self.reply(413, 'body missing or too large')
            try:
                data = json.loads(self.rfile.read(n))
                if not isinstance(data, dict): raise ValueError('expected a JSON object')
                with lock:
                    if route == '/feedback/send': out = {'sent': send_comments(d)}
                    else: out = {'id': add_comment(d, data.get('item'), data.get('text'))}
                    render(d, quiet=True)
            except ValueError as e: return self.reply(400, str(e))
            self.reply(200 if 'sent' in out else 201, json.dumps(out), 'application/json')
    return H


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('init'); p.add_argument('dir'); p.add_argument('--title', required=True); p.add_argument('--subtitle', default='')
    p = sub.add_parser('item'); p.add_argument('dir'); p.add_argument('id')
    for f in ('title', 'phase', 'status', 'note', 'rev'): p.add_argument('--' + f)
    p.add_argument('--link', nargs='*', default=[])
    p = sub.add_parser('link'); p.add_argument('dir'); p.add_argument('pairs', nargs='+')
    for c in ('block', 'ask'):
        p = sub.add_parser(c); p.add_argument('dir'); p.add_argument('text', nargs='?'); p.add_argument('--clear', action='store_true')
    p = sub.add_parser('log'); p.add_argument('dir'); p.add_argument('text')
    p = sub.add_parser('feedback'); p.add_argument('dir'); p.add_argument('--all', action='store_true')
    p.add_argument('--resolve', type=int, metavar='ID'); p.add_argument('--reply')
    p.add_argument('--wait', action='store_true', help='block until the human presses Send to Claude')
    p.add_argument('--timeout', type=float, metavar='S', help='with --wait: give up after S seconds (exit 3)')
    p = sub.add_parser('render'); p.add_argument('dir')
    p = sub.add_parser('serve'); p.add_argument('dir'); p.add_argument('--port', type=int, default=8765)
    p.add_argument('--no-mdserve', action='store_true', help='serve linked .md files as plain text')
    a = ap.parse_args(); d = a.dir
    if a.cmd == 'init':
        pathlib.Path(d).mkdir(parents=True, exist_ok=True)
        if path(d).exists(): sys.exit(f'{path(d)} exists')
        (pathlib.Path(d) / 'LOG.md').write_text(f'# {a.title} — log\n\nAppend-only, newest at bottom. Times are UTC.\n\n')
        save(d, {'title': a.title, 'subtitle': a.subtitle, 'items': [], 'links': {}, 'blockers': [], 'decisions': []})
    elif a.cmd == 'item':
        s = load(d); it = next((i for i in s['items'] if str(i['id']) == a.id), None)
        if it is None: it = {'id': a.id, 'title': a.title or a.id, 'status': 'todo'}; s['items'].append(it)
        for f in ('title', 'phase', 'status', 'note', 'rev'):
            if getattr(a, f) is not None: it[f] = getattr(a, f)
        if it['status'] not in STATUS: sys.exit(f'status must be one of {list(STATUS)}')
        for pair in a.link: l, u = pair.split('=', 1); it.setdefault('links', {})[l] = u
        save(d, s)
    elif a.cmd == 'link':
        s = load(d)
        for pair in a.pairs: l, u = pair.split('=', 1); s.setdefault('links', {})[l] = u
        save(d, s)
    elif a.cmd in ('block', 'ask'):
        s = load(d); key = 'blockers' if a.cmd == 'block' else 'decisions'
        s[key] = [] if a.clear else s.get(key, []) + ([a.text] if a.text else []); save(d, s)
    elif a.cmd == 'log':
        with open(pathlib.Path(d) / 'LOG.md', 'a') as fh: fh.write(f'- {now()} {a.text}\n')
        render(d)
    elif a.cmd == 'feedback':
        show = lambda c: print(f'#{c["id"]} [{stage(c)}] {"item " + str(c["item"]) if c.get("item") is not None else "general"} · {c.get("at", "")}: {c["text"]}'
                               + (f'\n    ↳ {c["reply"]}' if c.get('reply') else ''))
        if a.resolve is not None:
            with fb_lock(d):
                fb = load_fb(d); c = next((c for c in fb if c['id'] == a.resolve), None)
                if c is None: sys.exit(f'no comment #{a.resolve}')
                c.update(state='resolved', resolved_at=now(), **({'reply': a.reply} if a.reply else {}))
                save_fb(d, fb)
            render(d); return
        if a.wait:
            new = wait_sent(d, a.timeout)
            if not new: print('nothing sent'); sys.exit(3)
            for c in new: show(c)
            print(f'\nAct on each, then: tracker.py feedback {d} --resolve ID --reply "what you did"'); return
        shown = [c for c in load_fb(d) if a.all or c.get('state') != 'resolved']
        for c in shown: show(c)
        if not shown: print('no open comments' if not a.all else 'no comments')
    elif a.cmd == 'render':
        render(d)
    elif a.cmd == 'serve':
        render(d)
        md = None if a.no_mdserve else MdServers()
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))  # so atexit stops the mdserve children
        print(f'serving {d} on http://localhost:{a.port}' + ('' if md and md.exe else ' (markdown as plain text: mdserve not used)'))
        try: http.server.ThreadingHTTPServer(('127.0.0.1', a.port), handler(d, md)).serve_forever()
        except KeyboardInterrupt: pass


if __name__ == '__main__':
    main()
