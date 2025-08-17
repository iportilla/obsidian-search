# Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1     PIP_NO_CACHE_DIR=1     FLASK_ENV=production     BROWSE_ROOT=/vault     ALLOW_ANY_PATH=0

# tini for clean signal handling
RUN apt-get update && apt-get install -y --no-install-recommends tini   && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip &&     pip install -r /app/requirements.txt

# Copy app
COPY obsidian_search.py /app/

# A mount point for your Obsidian vault (bind from host)
VOLUME ["/vault"]

EXPOSE 5055

# Basic healthcheck
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3   CMD python - <<'PY'
import socket; s=socket.socket(); s.settimeout(2); s.connect(('127.0.0.1',5055)); s.close()
PY

ENTRYPOINT ["/usr/bin/tini", "--"]
# Safe default: root-limited to /vault; override ALLOW_ANY_PATH=1 at runtime if desired
CMD ["python", "obsidian_search.py", "--host", "0.0.0.0", "--port", "5055", "--browse-root", "/vault"]
