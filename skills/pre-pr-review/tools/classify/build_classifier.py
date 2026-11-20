"""Build classify-repos.html from repos.json (inventory of ~/code)."""
import json, re, sys, collections, html

src, dst = sys.argv[1], sys.argv[2]
repos = json.load(open(src))

def norm(origin):
    m = re.match(r'(?:git@|ssh://git@|https?://)(?:[^@/]+@)?([^:/]+)[:/](.+?)(?:\.git)?/?$', origin or "")
    if not m:
        return None
    host = re.sub(r'^ssh\.', '', m.group(1))
    parts = m.group(2).split('/')
    return host, parts[0], '/'.join(parts[1:]) or parts[0]

groups = collections.OrderedDict()
for r in repos:
    n = norm(r["origin"])
    if n:
        host, owner, name = n
        gkey = f"{host}/{owner}"
        key = f"{host}/{owner}/{name}"
    else:
        top = '/'.join(r["path"].split('/')[:3])
        gkey = f"(no origin) {top}"
        key = r["path"]
    groups.setdefault(gkey, []).append({"key": key, "path": r["path"], "origin": r["origin"] or "(none)"})

data = [{"group": g, "pattern": (g + "/*") if not g.startswith("(no origin)") else None, "repos": sorted(v, key=lambda x: x["key"])}
        for g, v in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))]

page = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>pre-pr-review: classify repos</title>
<style>
:root{--bg:#fafafa;--fg:#1a1a1a;--mut:#666;--line:#ddd;--on:#2b8a3e;--off:#868e96;--ask:#e67700;--sel:#e7f5ff}
@media (prefers-color-scheme:dark){:root{--bg:#141414;--fg:#e8e8e8;--mut:#999;--line:#333;--sel:#1c2b3a}}
*{box-sizing:border-box}body{font:14px/1.45 -apple-system,Helvetica,Arial,sans-serif;background:var(--bg);color:var(--fg);margin:0}
header{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);padding:12px 20px;z-index:5}
h1{font-size:17px;margin:0 0 4px}p.lead{margin:0 0 8px;color:var(--mut);max-width:900px}
.bar{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
input[type=search]{padding:6px 8px;width:280px;border:1px solid var(--line);border-radius:6px;background:transparent;color:var(--fg)}
button{padding:4px 10px;border:1px solid var(--line);border-radius:6px;background:transparent;color:var(--fg);cursor:pointer;font-size:13px}
button:hover{border-color:var(--fg)}
button.on{color:var(--on);border-color:var(--on)}button.off{color:var(--off);border-color:var(--off)}button.ask{color:var(--ask);border-color:var(--ask)}
.stats{color:var(--mut);margin-left:auto}
main{display:grid;grid-template-columns:1fr 380px;gap:20px;padding:16px 20px}
.group{border:1px solid var(--line);border-radius:8px;margin-bottom:10px}
.gh{display:flex;align-items:center;gap:8px;padding:8px 10px;cursor:pointer}
.gh .name{font-weight:600}.gh .count{color:var(--mut)}.gh .btns{margin-left:auto;display:flex;gap:4px}
.pill{font-size:11px;padding:1px 7px;border-radius:10px;color:#fff}
.pill.on{background:var(--on)}.pill.off{background:var(--off)}.pill.ask{background:var(--ask)}.pill.none{background:transparent;color:var(--mut);border:1px dashed var(--mut)}
.pill.mixed{background:transparent;color:var(--fg);border:1px solid var(--fg)}
ul{list-style:none;margin:0;padding:0 10px 8px 34px;display:none}.open ul{display:block}
li{display:flex;align-items:center;gap:8px;padding:2px 4px;border-radius:4px}li.sel{background:var(--sel)}
li .k{font-family:ui-monospace,Menlo,monospace;font-size:12.5px}li .p{color:var(--mut);font-size:12px}
li .eff{margin-left:auto}
aside{position:sticky;top:110px;align-self:start}
textarea{width:100%;height:420px;font:12px ui-monospace,Menlo,monospace;background:transparent;color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:8px}
.legend{font-size:12.5px;color:var(--mut);margin:6px 0 10px}
.legend b.on{color:var(--on)}.legend b.off{color:var(--off)}.legend b.ask{color:var(--ask)}
.hidden{display:none!important}
</style></head><body>
<header>
<h1>pre-pr-review: which repos get a review before a PR?</h1>
<p class="lead">Set a class per group (owner) or per repo. Repo choices override the group. Click a group to expand it. Tick repos, or use <b>shift-click</b> for a range, then use the buttons above to apply a class to all ticked ones. Your choices are saved in this browser. When you're done, use <b>Copy</b> or <b>Download</b> on the right, or tell Claude "done" and paste the rules.</p>
<div class="bar">
<input type="search" id="q" placeholder="filter: owner, repo or path…">
<span>Ticked:</span>
<button class="on" data-bulk="on">on</button><button class="off" data-bulk="off">off</button><button class="ask" data-bulk="ask">ask</button><button data-bulk="">clear</button>
<button id="clearsel">untick all</button>
<label><input type="checkbox" id="unclassified"> only unclassified</label>
<span class="stats" id="stats"></span>
</div>
</header>
<main>
<section id="list"></section>
<aside>
<div class="legend"><b class="on">on</b>: always review before a PR (unless the change is small) · <b class="off">off</b>: never · <b class="ask">ask</b>: Claude asks each time, depending on the change · <i>unset</i>: falls back to the default (on)</div>
<div class="bar" style="margin-bottom:6px"><button id="copy">Copy rules</button><button id="dl">Download rules</button><button id="reset">Reset all</button></div>
<textarea id="out" readonly></textarea>
</aside>
</main>
<script>
const DATA = __DATA__;
const LS = "pre-pr-review-classify-v1";
let st = JSON.parse(localStorage.getItem(LS) || '{"g":{},"r":{}}');
const sel = new Set(); let lastIdx = null; const flat = [];
const save = () => localStorage.setItem(LS, JSON.stringify(st));
const pill = c => `<span class="pill ${c||'none'}">${c||'unset'}</span>`;
function eff(g, r){ return st.r[r.key] || st.g[g.group] || ""; }
function render(){
  const q = document.getElementById('q').value.toLowerCase(), onlyU = document.getElementById('unclassified').checked;
  const L = document.getElementById('list'); const openSet = new Set([...L.querySelectorAll('.group.open')].map(e=>e.dataset.g));
  L.innerHTML = ""; flat.length = 0;
  DATA.forEach(g => {
    const rs = g.repos.filter(r => (!q || (g.group+' '+r.key+' '+r.path).toLowerCase().includes(q)) && (!onlyU || !eff(g,r)));
    if(!rs.length) return;
    const effs = new Set(g.repos.map(r=>eff(g,r)));
    const gc = st.g[g.group]||"", mixed = effs.size>1;
    const d = document.createElement('div'); d.className = 'group'+(openSet.has(g.group)||q?' open':''); d.dataset.g = g.group;
    d.innerHTML = `<div class="gh"><input type="checkbox" class="gsel" title="tick all shown repos in this group"><span class="name">${g.group}</span><span class="count">${g.repos.length} repo${g.repos.length>1?'s':''}</span>${mixed?'<span class="pill mixed">mixed</span>':pill(gc)}
      <span class="btns">${g.pattern?['on','off','ask',''].map(c=>`<button class="${c}" data-g="${c}">${c||'clear'}</button>`).join(''):'<span class="p">no remote: set per repo</span>'}</span></div><ul></ul>`;
    const ul = d.querySelector('ul');
    rs.forEach(r => { const i = flat.length; flat.push(r.key);
      const li = document.createElement('li'); if(sel.has(r.key)) li.classList.add('sel');
      li.innerHTML = `<input type="checkbox" ${sel.has(r.key)?'checked':''}><span class="k">${r.key}</span><span class="p">${r.path}</span><span class="eff">${st.r[r.key]?pill(st.r[r.key])+' <small>(own)</small>':pill(eff(g,r))}</span>`;
      li.querySelector('input').addEventListener('click', e => { e.stopPropagation();
        if(e.shiftKey && lastIdx!==null){ const [a,b]=[Math.min(lastIdx,i),Math.max(lastIdx,i)]; for(let j=a;j<=b;j++) sel.add(flat[j]); }
        else { e.target.checked ? sel.add(r.key) : sel.delete(r.key); }
        lastIdx = i; render(); });
      ul.appendChild(li); });
    d.querySelector('.gh').addEventListener('click', e => { if(e.target.closest('button,input')) return; d.classList.toggle('open'); });
    d.querySelector('.gsel').addEventListener('click', e => { e.stopPropagation(); rs.forEach(r => e.target.checked ? sel.add(r.key) : sel.delete(r.key)); render(); });
    d.querySelectorAll('[data-g]').forEach(b => b.addEventListener('click', e => { e.stopPropagation(); const c=b.dataset.g; if(c) st.g[g.group]=c; else delete st.g[g.group]; save(); render(); }));
    L.appendChild(d);
  });
  out(); stats();
}
function stats(){ let n={on:0,off:0,ask:0,'':0}, t=0; DATA.forEach(g=>g.repos.forEach(r=>{n[eff(g,r)]++;t++;}));
  document.getElementById('stats').textContent = `${t} repos · on ${n.on} · off ${n.off} · ask ${n.ask} · unset ${n['']} · ticked ${sel.size}`; }
function out(){
  const lines = ["# ~/.config/pre-pr-review/rules  (generated "+new Date().toISOString().slice(0,10)+")",
    "# pattern                                   class   (on | off | ask; most specific match wins; unmatched → on)"];
  const pad = s => s.padEnd(44);
  DATA.forEach(g => { const gc = st.g[g.group]; const own = g.repos.filter(r=>st.r[r.key] && st.r[r.key]!==gc);
    if(!gc && !own.length) return; lines.push("");
    if(gc && g.pattern) lines.push(pad(g.pattern)+gc);
    own.forEach(r => lines.push(pad(r.key)+st.r[r.key])); });
  document.getElementById('out').value = lines.join("\n")+"\n";
}
document.querySelectorAll('[data-bulk]').forEach(b => b.addEventListener('click', () => {
  const c = b.dataset.bulk; sel.forEach(k => { if(c) st.r[k]=c; else delete st.r[k]; }); save(); render(); }));
document.getElementById('clearsel').onclick = () => { sel.clear(); lastIdx=null; render(); };
document.getElementById('q').oninput = render; document.getElementById('unclassified').onchange = render;
document.getElementById('copy').onclick = () => navigator.clipboard.writeText(document.getElementById('out').value);
document.getElementById('dl').onclick = () => { const a=document.createElement('a'); a.href=URL.createObjectURL(new Blob([document.getElementById('out').value],{type:'text/plain'})); a.download='rules'; a.click(); };
document.getElementById('reset').onclick = () => { st={g:{},r:{}}; save(); sel.clear(); render(); };
render();
</script></body></html>"""
open(dst, "w").write(page.replace("__DATA__", json.dumps(data)))
print(f"{sum(len(g['repos']) for g in data)} repos in {len(data)} groups -> {dst}")
