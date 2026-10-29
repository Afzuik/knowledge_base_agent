#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ ! -f "$ROOT/frontend/dist/index.html" ]]; then
  echo 'Frontend missing: install frontend dependencies and run npm run build first.' >&2
  exit 1
fi
if [[ ! -x "$ROOT/backend/.venv/bin/python" ]]; then
  echo 'Backend environment missing: run uv sync --frozen in backend first.' >&2
  exit 1
fi
cd "$ROOT/backend"
echo 'Local ingestion app: http://127.0.0.1:8765 — upload and parsing ready; no models or Q&A.'
exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
