#!/usr/bin/env python3
"""Live task tracker: one status.json drives a local HTML page (index.html) that a human keeps open.

usage:
  tracker.py init  <dir> --title "Final review" [--subtitle "..."]
  tracker.py item  <dir> <id> [--title T] [--phase P] [--status S] [--note N] [--rev R] [--link LABEL=URL ...]
  tracker.py link  <dir> LABEL=URL [...]          top-of-page links (reports, sheets, PRs)
  tracker.py block <dir> "text" | --clear         blockers panel (red)
  tracker.py ask   <dir> "text" | --clear         decisions-for-the-human panel (amber)
  tracker.py log   <dir> "text"                   append a timestamped line to <dir>/LOG.md (append-only)
  tracker.py render <dir>                         rebuild <dir>/index.html (every other command also renders)
  tracker.py serve <dir> [--port 8765] [--no-mdserve]
                                                  serve <dir> on http://localhost:<port> (foreground)

Statuses: todo, in-progress, review, decision, blocked, done.
Notes, links and log lines are linkified: http(s) URLs, and relative paths to files in <dir> (e.g. reports/x.md).
The page reloads itself every 30 s, so it stays current while the task runs.

Markdown links (relative *.md, including ../ paths elsewhere in the repo) open formatted: the page links
them as /md?p=<path>, and `serve` starts one `mdserve` per folder on demand (mdserve only serves a flat
folder) and redirects there. Targets must sit inside the git repo that holds <dir>. Without mdserve on
PATH, or with --no-mdserve, the file is served as plain text.
"""
import argparse, datetime, html, json, pathlib, re, sys, http.server
import atexit, shutil, signal, socket, subprocess, threading, time, urllib.parse

STATUS = {  # icon, label, css class
    'done': ('✅', 'Done'), 'review': ('⬜', 'Ready for review'), 'in-progress': ('⏳', 'In progress'),
    'decision': ('❓', 'Needs a decision'), 'blocked': ('⛔', 'Blocked'), 'todo': ('·', 'Not started'),
}
THEME = """:root{--bg:#f7f7f5;--card:#fff;--ink:#1d1d1f;--mute:#6b6b70;--line:#e3e3e0;--acc:#2f5bd3;--ok:#1f7a3f;--warn:#9a6700;--q:#a33a1f;--ph:#efefec;--ins:#dff3e4;--del:#fbe2df}
@media (prefers-color-scheme:dark){:root{--bg:#141416;--card:#1d1d20;--ink:#ececee;--mute:#9a9aa2;--line:#2e2e33;--acc:#7d9bff;--ok:#5fd18a;--warn:#e3b341;--q:#f08a6c;--ph:#252529;--ins:#1f3a27;--del:#432421}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
a{color:var(--acc)}main{max-width:1100px;margin:0 auto;padding:24px 16px}h1{font-size:22px;margin:0 0 4px}.sub{color:var(--mute);margin:0 0 12px}"""


def now(): return datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
def path(d): return pathlib.Path(d) / 'status.json'
def load(d):
    p = path(d)
    if not p.exists(): sys.exit(f'{p} not found — run: tracker.py init {d} --title ...')
    return json.loads(p.read_text())
def save(d, s):
    s['updated'] = now(); path(d).write_text(json.dumps(s, indent=1, ensure_ascii=False)); render(d, s)


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


def render(d, s=None):
    s = s or load(d); items = s.get('items', [])
    counts = {k: sum(i['status'] == k for i in items) for k in STATUS}
    pct = round(100 * counts['done'] / len(items)) if items else 0
    rows, phase = [], object()
    for i in items:
        if i.get('phase') != phase:
            phase = i.get('phase'); grp = [x for x in items if x.get('phase') == phase]
            if phase: rows.append(f'<tr class="ph"><th colspan="4">{html.escape(phase)}<span>{sum(x["status"]=="done" for x in grp)}/{len(grp)}</span></th></tr>')
        icon, lab = STATUS.get(i['status'], ('?', i['status']))
        links = ' · '.join(f'<a href="{html.escape(mdlink(u))}">{html.escape(l)}</a>' for l, u in (i.get('links') or {}).items())
        note = (f'<div class="note">{linkify(i["note"], d)}</div>' if i.get('note') else '') + (f'<div class="note">{links}</div>' if links else '')
        rows.append(f'<tr class="{i["status"]}"><td class="st" title="{lab}">{icon}</td><td class="n">{html.escape(str(i["id"]))}</td>'
                    f'<td><b>{html.escape(i.get("title", ""))}</b>{note}</td><td class="lab">{lab}<div class="rev">{html.escape(i.get("rev", ""))}</div></td></tr>')
    panel = lambda key, cls, head: (f'<div class="blk {cls}"><b>{head}</b><ul>' + ''.join(f'<li>{linkify(x, d)}</li>' for x in s.get(key, [])) + '</ul></div>') if s.get(key) else ''
    top = ' · '.join(f'<a href="{html.escape(mdlink(u))}">{html.escape(l)}</a>' for l, u in (s.get('links') or {}).items())
    if (pathlib.Path(d) / 'LOG.md').exists(): top = (top + ' · ' if top else '') + f'<a href="{mdlink("LOG.md")}">LOG.md</a>'
    summary = ' · '.join(f'{STATUS[k][0]} {v} {STATUS[k][1].lower()}' for k, v in counts.items() if v)
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="30">
<title>{html.escape(s.get("title", "Tracker"))}</title><style>{THEME}
.bar{{height:8px;background:var(--line);border-radius:4px;margin:0 0 16px;overflow:hidden}}.bar i{{display:block;height:100%;width:{pct}%;background:var(--ok)}}
.wrap{{overflow-x:auto}}table{{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}}
td,th{{text-align:left;padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top}}tr.ph th{{background:var(--ph);font-size:13px;color:var(--mute)}}tr.ph span{{float:right;font-weight:500}}
td.st{{font-size:18px;width:36px;text-align:center}}td.n{{width:40px;color:var(--mute)}}.note{{font-size:13px;color:var(--mute);margin-top:2px}}td.lab{{font-size:13px;white-space:nowrap}}
.rev{{color:var(--mute);font-family:ui-monospace,monospace;font-size:12px}}tr.done td.lab{{color:var(--ok)}}tr.done b{{font-weight:500;text-decoration:line-through;text-decoration-color:var(--mute)}}
tr.in-progress td.lab{{color:var(--warn)}}tr.decision td.lab,tr.blocked td.lab{{color:var(--q)}}
.blk{{background:var(--card);border:1px solid var(--q);border-radius:12px;padding:10px 14px;margin:0 0 12px}}.blk.ask{{border-color:var(--warn)}}.blk ul{{margin:4px 0 0;padding-left:18px}}</style></head>
<body><main><h1>{html.escape(s.get("title", "Tracker"))}</h1>
<p class="sub">{linkify(s.get("subtitle", ""), d)}{"<br>" if s.get("subtitle") else ""}Updated {html.escape(s.get("updated", ""))} · {pct}% done · {summary}{"<br>" + top if top else ""}</p>
<div class="bar"><i></i></div>{panel("blockers", "", "⛔ Blockers")}{panel("decisions", "ask", "❓ Decisions needed")}
<div class="wrap"><table><tbody>{"".join(rows)}</tbody></table></div></main></body></html>'''
    (pathlib.Path(d) / 'index.html').write_text(page)
    print(f'index.html: {summary or "no items"}')


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
    base = pathlib.Path(d).resolve()
    top = subprocess.run(['git', '-C', str(base), 'rev-parse', '--show-toplevel'], capture_output=True, text=True)
    root = pathlib.Path(top.stdout.strip()).resolve() if top.returncode == 0 else base

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k): super().__init__(*a, directory=d, **k)
        def log_message(self, *a): pass
        def do_GET(self):
            u = urllib.parse.urlsplit(self.path)
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
    p = sub.add_parser('render'); p.add_argument('dir')
    p = sub.add_parser('serve'); p.add_argument('dir'); p.add_argument('--port', type=int, default=8765)
    p.add_argument('--no-mdserve', action='store_true', help='serve linked .md files as plain text')
    a = ap.parse_args(); d = a.dir
    if a.cmd == 'init':
        pathlib.Path(d).mkdir(parents=True, exist_ok=True)
        if path(d).exists(): sys.exit(f'{path(d)} exists')
        save(d, {'title': a.title, 'subtitle': a.subtitle, 'items': [], 'links': {}, 'blockers': [], 'decisions': []})
        (pathlib.Path(d) / 'LOG.md').write_text(f'# {a.title} — log\n\nAppend-only, newest at bottom.\n\n')
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
