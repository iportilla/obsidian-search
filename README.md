# Obsidian Search

A lightweight **Flask-based** web app to browse, index, and search your Obsidian vault — and open results directly in the Obsidian desktop app via `obsidian://` links.

## ✨ Features
- 📂 Visual **vault browser** (with breadcrumb)
- 🔍 **Full-text search** over `.md` files
- 🔗 **Open in Obsidian** (`vault+file` or `path` deep links)
- 🐳 **Dockerized** with `Makefile` (start/stop/logs)
- 🔐 Safe **root-limited** browsing or optional **browse-anywhere** mode

## 🚀 Quick Start (Local)
```bash
pip install -r requirements.txt
python obsidian_search.py --host 127.0.0.1 --port 5055 --browse-root "/Users/you"
# open http://127.0.0.1:5055
```

**Tip:** enable browse-anywhere mode:
```bash
python obsidian_search.py --host 127.0.0.1 --port 5055 --allow-any-path
```

## 🐳 Quick Start (Docker)
```bash
make build
make start VAULT="/Users/you/ObsidianVault" VAULT_NAME="My Vault Name"
# open http://127.0.0.1:5055
```

- If you pass `VAULT_NAME`, links use `obsidian://open?vault=<name>&file=<relpath>`.
- Otherwise, set both `CONTAINER_PREFIX` and `HOST_PREFIX` to map container paths → host paths
  for `obsidian://open?path=...` deep links.

## ⚙️ Makefile parameters
- `VAULT` — host path you bind into container as `/vault`
- `VAULT_NAME` — Obsidian vault display name (enables `vault+file` links)
- `CONTAINER_PREFIX` — usually `/vault`
- `HOST_PREFIX` — host path to the same folder as `/vault`
- `ALLOW_ANY` — `0` safe, `1` browse anywhere inside the container

## 🔎 Verify container is running
```bash
docker ps
docker logs -f obsidian-search
```

## 📝 License
MIT
