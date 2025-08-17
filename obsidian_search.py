#!/usr/bin/env python3
import os
import argparse
from pathlib import Path
from urllib.parse import quote
from flask import Flask, request, jsonify, render_template_string, abort

app = Flask(__name__)

# ---------------- Config (module-level defaults; can be overridden by env/CLI) ----------------
BROWSE_ROOT = os.path.abspath(os.environ.get("BROWSE_ROOT", os.path.expanduser("~")))
ALLOW_ANY_PATH = os.environ.get("ALLOW_ANY_PATH", "0") == "1"

# Obsidian deep-link configuration
OBSIDIAN_CONTAINER_PREFIX = os.path.normpath(os.environ.get("OBSIDIAN_CONTAINER_PREFIX", "/vault"))
OBSIDIAN_HOST_PREFIX = os.path.normpath(os.environ.get("OBSIDIAN_HOST_PREFIX", ""))
# If you know your Obsidian vault display name, set this and we’ll use vault+file deep links.
OBSIDIAN_VAULT_NAME = os.environ.get("OBSIDIAN_VAULT_NAME", "")

# ---------------- In-memory state ----------------
INDEX = []   # list[(doc_id, text)]
DOCS = {}    # doc_id -> {title, content, path, rel_path}
VAULT_PATH = None  # absolute path to selected vault (container-visible if in Docker)


# ---------------- Helpers ----------------
def within_root(p: Path) -> bool:
    """If allow-any-path is enabled, all paths are allowed; otherwise restrict to BROWSE_ROOT."""
    if ALLOW_ANY_PATH:
        return True
    try:
        return os.path.commonpath([p.resolve(strict=False), Path(BROWSE_ROOT).resolve(strict=False)]) == str(
            Path(BROWSE_ROOT).resolve(strict=False)
        )
    except Exception:
        return False


def crawl_obsidian_vault(folder_path: str):
    """Index all .md files under folder_path."""
    index = []
    docs = {}
    doc_id = 0
    for root, _, files in os.walk(folder_path):
        for file in files:
            if not file.lower().endswith(".md"):
                continue
            path = os.path.join(root, file)
            try:
                text = Path(path).read_text(encoding="utf-8", errors="ignore")
            except Exception:
                text = ""
            title = os.path.splitext(file)[0]
            rel_path = os.path.relpath(path, folder_path)
            docs[doc_id] = {
                "title": title,
                "content": text,
                "path": str(Path(path).resolve()),
                "rel_path": rel_path
            }
            index.append((doc_id, text))
            doc_id += 1
    return index, docs


def system_root_for(path: Path) -> Path:
    """Return filesystem root for a given path (handles Windows drive roots safely)."""
    p = path.resolve(strict=False)
    if os.name == "nt":
        anchor = p.anchor if p.anchor else (p.drive + os.sep)  # e.g., 'C:\\'
        return Path(anchor)
    return Path("/")


def map_container_to_host(abs_path: str) -> str:
    """
    Map a container path (e.g., /vault/Notes/Foo.md) to the host path
    (e.g., /Users/you/ObsidianVault/Notes/Foo.md) using the configured prefixes.
    If prefixes aren't set, returns the original path.
    """
    if OBSIDIAN_CONTAINER_PREFIX and OBSIDIAN_HOST_PREFIX:
        cp = os.path.normpath(OBSIDIAN_CONTAINER_PREFIX)
        hp = os.path.normpath(OBSIDIAN_HOST_PREFIX)
        ap = os.path.normpath(abs_path)
        if ap == cp:
            return hp
        if ap.startswith(cp + os.sep):
            return hp + ap[len(cp):]
    return abs_path


def build_obsidian_url(meta: dict) -> str:
    """
    Prefer vault+file form when OBSIDIAN_VAULT_NAME is set.
    Otherwise use path= with a mapped host path.
    """
    if OBSIDIAN_VAULT_NAME and VAULT_PATH:
        try:
            rel = Path(meta["path"]).resolve().relative_to(Path(VAULT_PATH).resolve())
            rel_posix = rel.as_posix()
        except Exception:
            rel_posix = Path(meta.get("rel_path") or os.path.basename(meta["path"])).as_posix()
        return f"obsidian://open?vault={quote(OBSIDIAN_VAULT_NAME)}&file={quote(rel_posix)}"
    else:
        host_path = map_container_to_host(meta["path"])
        return f"obsidian://open?path={quote(host_path)}"


# ---------------- UI (HTML) ----------------
PAGE = r"""
<!doctype html>
<meta charset="utf-8"/>
<title>Obsidian Vault — Browse & Search</title>
<style>
  :root {
    --bg: #0b1020;           --panel: #11172a;      --muted: #9aa4b2;
    --text: #e6eef8;         --edge: #1e2a44;       --accent: #0ea5e9;
  }
  *{box-sizing:border-box}
  body{margin:0; font-family:system-ui,Segoe UI,Arial,sans-serif; background:var(--bg); color:var(--text);}
  .layout{display:grid; grid-template-columns: 240px 1fr; height:100vh;}
  .sidebar{background:linear-gradient(180deg,#0f152a,#0b1020); border-right:1px solid var(--edge); padding:16px; position:relative;}
  .brand{font-weight:800; letter-spacing:.3px; margin:4px 0 12px 8px;}
  .nav{display:flex; flex-direction:column; gap:8px; margin-top:8px;}
  .nav button{
    display:flex; align-items:center; gap:10px;
    padding:10px 12px; border:1px solid var(--edge); background:#0f162d; color:var(--text);
    border-radius:10px; cursor:pointer; text-align:left; font-size:14px;
  }
  .nav button.active{ background: #162443; border-color:#24406f; box-shadow: inset 0 0 0 1px #274b86; }
  .nav button .dot{width:8px;height:8px;border-radius:50%; background:#6b7280}
  .nav button.active .dot{background:var(--accent)}
  .footer{position:absolute; bottom:12px; left:16px; right:16px; color:var(--muted); font-size:12px;}

  .main{padding:20px; overflow:auto;}
  .panel{background:var(--panel); border:1px solid var(--edge); border-radius:14px; padding:16px;}
  .title{display:flex; align-items:center; justify-content:space-between; margin:0 0 12px 0; font-size:18px; font-weight:800;}
  .muted{color:var(--muted)}
  .mono{font-family: ui-monospace, SFMono-Regular, Menlo, monospace;}
  .row{display:flex; gap:10px; align-items:center; flex-wrap:wrap;}
  input[type=text]{flex:1 1 340px; min-width:260px; padding:10px 12px; border-radius:10px; border:1px solid var(--edge); background:#0e1528; color:var(--text)}
  button{padding:10px 14px; border-radius:10px; border:1px solid var(--edge); background:#0e1528; color:#e6eef8; cursor:pointer}
  button.primary{background:var(--accent); border-color:var(--accent); color:#04121a;}
  button.ghost{background:#0e1528}
  .spacer{height:14px}

  .breadcrumb a{color:#9bd3ff; text-decoration:none; margin-right:6px}
  .list{border:1px solid var(--edge); border-radius:10px; overflow:hidden}
  .item{display:flex; align-items:center; gap:10px; padding:10px 12px; border-bottom:1px solid var(--edge); cursor:pointer}
  .item:hover{background:#101a33}
  .item:last-child{border-bottom:0}
  .result{padding:10px 12px; border-bottom:1px solid var(--edge)}
  .result a{color:#9bd3ff; text-decoration:none; font-weight:700}
  .result small{display:block; color:var(--muted)}
  .empty{padding:10px 12px; color:var(--muted); font-style:italic}
  .pill{display:inline-block; margin-left:8px; padding:2px 6px; font-size:11px; border:1px solid var(--edge); border-radius:999px; color:var(--muted)}
</style>

<div class="layout">
  <aside class="sidebar">
    <div class="brand">📔 Obsidian Tools</div>
    <div class="nav">
      <button id="tab-browse" class="active" onclick="switchTab('browse')"><span class="dot"></span> Browse Library</button>
      <button id="tab-search" onclick="switchTab('search')"><span class="dot"></span> Run a Search</button>
    </div>
    <div class="footer muted">
      {{ footer_note }}<br/>
      Start: <span class="mono">{{ root }}</span><br/>
      Vault: <span id="vaultLabel" class="mono">—</span>
    </div>
  </aside>

  <main class="main">
    <!-- Browse Panel -->
    <section id="panel-browse" class="panel">
      <div class="title">
        <div>Choose Vault Folder</div>
        <div class="muted">{{ browse_hint }}</div>
      </div>
      <div id="crumbs" class="breadcrumb"></div>
      <div class="spacer"></div>
      <div id="listing" class="list"></div>
      <div class="spacer"></div>
      <div class="row">
        <button id="chooseBtn" class="primary" disabled>Use This Folder</button>
        <button class="ghost" onclick="refresh()">Refresh</button>
        <span id="chosen" class="muted"></span>
      </div>
    </section>

    <!-- Search Panel -->
    <section id="panel-search" class="panel" style="display:none">
      <div class="title">
        <div>Search Notes</div>
        <div class="muted">Results open in <strong>Obsidian</strong> via obsidian:// links<span class="pill">fallback: browser</span></div>
      </div>
      <div class="row">
        <input id="q" type="text" placeholder="Search title or content…">
        <button class="primary" onclick="doSearch()">Search</button>
      </div>
      <div id="searchMeta" class="muted" style="margin-top:8px;"></div>
      <div class="spacer"></div>
      <div id="results" class="list"></div>
    </section>
  </main>
</div>

<script>
let currentPath = "{{ root }}";
let selectedPath = null;
let currentVault = null;

function switchTab(which){
  const tabs = ['browse','search'];
  tabs.forEach(t=>{
    document.getElementById('panel-'+t).style.display = (t===which)?'block':'none';
    document.getElementById('tab-'+t).classList.toggle('active', t===which);
  });
}

function refresh(){ listDir(currentPath); }

async function listDir(path){
  const res = await fetch(`/api/ls?path=${encodeURIComponent(path)}`);
  if(!res.ok){ alert('Failed to list directory'); return; }
  const data = await res.json();
  renderBreadcrumb(data.breadcrumb);
  renderListing(data);
}

function renderBreadcrumb(crumbs){
  const c = document.getElementById('crumbs');
  c.innerHTML='';
  const makeLink = (label, path) => {
    const a = document.createElement('a');
    a.textContent = label;
    a.href = '#';
    a.onclick = (e)=>{ e.preventDefault(); currentPath = path; listDir(currentPath); };
    return a;
  };
  crumbs.forEach((part, i) => {
    c.appendChild(makeLink(part.label, part.path));
    if(i < crumbs.length - 1) c.appendChild(document.createTextNode(' / '));
  });
}

function renderListing(data){
  const cont = document.getElementById('listing');
  cont.innerHTML='';
  if(data.parent){
    const up = document.createElement('div');
    up.className='item';
    up.textContent = '📁 ..';
    up.onclick = ()=>{ currentPath = data.parent; listDir(currentPath); };
    cont.appendChild(up);
  }
  if(data.dirs.length===0 && data.files.length===0){
    const e=document.createElement('div'); e.className='empty'; e.textContent='(empty)'; cont.appendChild(e);
  }
  data.dirs.forEach(d=>{
    const el = document.createElement('div');
    el.className='item';
    el.textContent = '📁 ' + d.name;
    el.onclick = ()=>{ currentPath = d.path; listDir(currentPath); };
    cont.appendChild(el);
  });
  data.files.forEach(f=>{
    const el = document.createElement('div');
    el.className='item';
    el.textContent = '📄 ' + f.name;
    cont.appendChild(el);
  });

  selectedPath = data.path;
  document.getElementById('chooseBtn').disabled = false;
  document.getElementById('chosen').textContent = selectedPath;
}

document.getElementById('chooseBtn').onclick = async ()=>{
  const res = await fetch('/api/set_vault', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ path: selectedPath })
  });
  if(!res.ok){ const t = await res.text(); alert('Failed to set vault: ' + t); return; }
  const data = await res.json();
  currentVault = data.vault;
  document.getElementById('vaultLabel').textContent = currentVault;
  alert(`Vault loaded. Indexed ${data.count} notes.`);
  switchTab('search');
};

async function doSearch(){
  const q = document.getElementById('q').value.trim();
  const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
  const data = await res.json();
  const results = document.getElementById('results');
  const meta = document.getElementById('searchMeta');
  results.innerHTML='';
  meta.textContent = q ? `Found ${data.length} matches` : 'Enter a query to search.';
  if(data.length === 0){
    const e=document.createElement('div'); e.className='empty'; e.textContent='No results'; results.appendChild(e);
    return;
  }
  data.forEach(r=>{
    const div = document.createElement('div'); div.className='result';
    const a = document.createElement('a'); a.href = r.obsidian_url; a.textContent = r.title; a.title = 'Open in Obsidian';
    const fallback = document.createElement('a');
    fallback.href = '/open?doc_id=' + r.id;
    fallback.textContent = ' (view)';
    fallback.style.color = '#9aa4b2';
    fallback.style.fontWeight = '400';
    fallback.style.textDecoration = 'none';
    const s = document.createElement('small'); s.textContent = r.rel_path;

    div.appendChild(a);
    div.appendChild(fallback);
    div.appendChild(s);
    results.appendChild(div);
  });
}

// init
listDir(currentPath);
</script>
"""

# ---------------- Routes ----------------
@app.route("/")
def home():
    footer_note = "Browse anywhere on this machine (unsafe mode)" if ALLOW_ANY_PATH \
                  else "Browsing is limited to the configured root"
    browse_hint = "Full filesystem access enabled" if ALLOW_ANY_PATH \
                  else "Tip: start server with --allow-any-path to browse anywhere"
    return render_template_string(PAGE, root=BROWSE_ROOT, footer_note=footer_note, browse_hint=browse_hint)


@app.route("/api/ls")
def api_ls():
    raw = request.args.get("path", BROWSE_ROOT)
    path = Path(raw).expanduser().resolve(strict=False)

    if not within_root(path):
        abort(403, description="Path outside of allowed root")
    if not path.exists() or not path.is_dir():
        abort(400, description="Not a directory")

    # Breadcrumbs & parent
    if ALLOW_ANY_PATH:
        root = system_root_for(path)
        current = root
        crumbs = [{"label": str(root), "path": str(root)}]
        rel_parts = path.resolve(strict=False).parts[len(root.resolve(strict=False).parts):]
        for part in rel_parts:
            current = current.joinpath(part)
            crumbs.append({"label": part, "path": str(current)})
        parent = str(path.parent) if path != root else None
    else:
        base = Path(BROWSE_ROOT).resolve(strict=False)
        crumbs = [{"label": str(base), "path": str(base)}]
        try:
            rel = path.relative_to(base)
            current = base
            for part in rel.parts:
                current = current.joinpath(part)
                crumbs.append({"label": part, "path": str(current)})
        except ValueError:
            pass
        parent = str(path.parent) if path != base else None

    dirs, files = [], []
    try:
        entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except PermissionError:
        abort(403, description="Permission denied")
    for entry in entries:
        try:
            if entry.is_dir():
                if within_root(entry):
                    dirs.append({"name": entry.name, "path": str(entry.resolve(strict=False))})
            else:
                files.append({"name": entry.name, "path": str(entry.resolve(strict=False))})
        except Exception:
            continue

    return jsonify({
        "path": str(path),
        "parent": parent,
        "breadcrumb": crumbs,
        "dirs": dirs,
        "files": files
    })


@app.route("/api/set_vault", methods=["POST"])
def api_set_vault():
    global INDEX, DOCS, VAULT_PATH
    data = request.get_json(force=True, silent=True) or {}
    req_path = data.get("path", "")

    if not req_path:
        abort(400, description="Missing path")

    path = Path(req_path).expanduser().resolve(strict=False)
    if not within_root(path):
        abort(403, description="Path outside of allowed root")
    if not path.is_dir():
        abort(400, description="Not a directory")

    VAULT_PATH = str(path)  # container-visible absolute
    INDEX, DOCS = crawl_obsidian_vault(VAULT_PATH)
    return jsonify({"ok": True, "count": len(DOCS), "vault": VAULT_PATH})


@app.route("/api/search")
def api_search():
    q = (request.args.get("q") or "").strip().lower()
    if not q:
        return jsonify([])
    results = []
    for doc_id, text in INDEX:
        meta = DOCS.get(doc_id)
        if not meta:
            continue
        hay = (text or "").lower()
        title = (meta["title"] or "").lower()
        if q in hay or q in title:
            results.append({
                "id": doc_id,
                "title": meta["title"],
                "rel_path": meta["rel_path"],
                "abs_path": meta["path"],                 # container-visible path
                "obsidian_url": build_obsidian_url(meta)  # deep link to host/vault
            })
    return jsonify(results)


@app.route("/open")
def open_doc():
    """Browser fallback: render the markdown content."""
    try:
        doc_id = int(request.args.get("doc_id", "-1"))
    except ValueError:
        abort(400, description="Invalid doc id")
    meta = DOCS.get(doc_id)
    if not meta:
        abort(404, description="Document not found")
    return f"""
    <div style="padding:20px; font-family:system-ui,Segoe UI,Arial,sans-serif; color:#e6eef8; background:#0b1020">
      <a href="/" style="color:#9bd3ff; text-decoration:none">← Back</a>
      <h2>{meta['title']}</h2>
      <div style="color:#9aa4b2; font-size:12px; margin-bottom:10px">{meta['rel_path']}</div>
      <pre style="white-space:pre-wrap; border:1px solid #1e2a44; background:#0f162d; padding:14px; border-radius:12px; overflow:auto">{meta['content']}</pre>
    </div>
    """


# ---------------- Main ----------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Obsidian vault browser + search (opens notes in Obsidian)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5055)
    parser.add_argument("--browse-root", default=BROWSE_ROOT,
                        help="Starting folder for browsing (ignored if --allow-any-path).")
    parser.add_argument("--allow-any-path", action="store_true",
                        help="Allow browsing anywhere on the filesystem (unsafe).")
    parser.add_argument("--vault-name", default=OBSIDIAN_VAULT_NAME,
                        help="Obsidian vault display name (enables obsidian://open?vault=...&file=... links).")
    parser.add_argument("--container-prefix", default=OBSIDIAN_CONTAINER_PREFIX,
                        help="Container path prefix (e.g., /vault) to translate to host path.")
    parser.add_argument("--host-prefix", default=OBSIDIAN_HOST_PREFIX,
                        help="Host path prefix (e.g., /Users/you/ObsidianVault) for deep-link mapping.")
    args = parser.parse_args()

    # Assign module-level variables from CLI where provided
    ALLOW_ANY_PATH = bool(args.allow_any_path) or ALLOW_ANY_PATH
    BROWSE_ROOT = os.path.abspath(args.browse_root)
    OBSIDIAN_VAULT_NAME = args.vault_name or OBSIDIAN_VAULT_NAME
    OBSIDIAN_CONTAINER_PREFIX = os.path.normpath(args.container_prefix or OBSIDIAN_CONTAINER_PREFIX)
    OBSIDIAN_HOST_PREFIX = os.path.normpath(args.host_prefix or OBSIDIAN_HOST_PREFIX)

    # Ensure starting folder exists
    os.makedirs(BROWSE_ROOT, exist_ok=True)

    mode = "UNSAFE: any path" if ALLOW_ANY_PATH else f"root-limited: {BROWSE_ROOT}"
    print(f"[info] Browse mode: {mode}")
    print(f"[info] Obsidian link mode: {'vault+file' if OBSIDIAN_VAULT_NAME else 'absolute path'}")
    if not OBSIDIAN_VAULT_NAME:
        print(f"[info] Path mapping: {OBSIDIAN_CONTAINER_PREFIX}  ->  {OBSIDIAN_HOST_PREFIX or '(no host prefix; using container path)'}")

    app.run(host=args.host, port=args.port, debug=True)
