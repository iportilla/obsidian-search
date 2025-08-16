# Obsidian Search

A tiny Flask-based search UI for your Obsidian notes.  
Supports browsing, searching, and opening notes in Obsidian.

## Features
- Browse vault safely (restricted root).
- Search across Markdown files.
- Open results directly in Obsidian.

## Run Locally
```bash
pip install -r requirements.txt
python obsidian_search.py --host 127.0.0.1 --port 5055 --browse-root "/path/to/obsidian"
```

## Run with Docker
```bash
make build
make start VAULT="/path/to/your/vault" VAULT_NAME="VaultName"
```
