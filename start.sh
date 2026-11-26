#!/usr/bin/env sh
# EcoByte one-command start (macOS/Linux/Git Bash). First run installs everything and seeds demo data.
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/backend"
[ -d .venv ] || python3 -m venv .venv || python -m venv .venv
PY=.venv/bin/python; [ -x "$PY" ] || PY=.venv/Scripts/python
"$PY" -m pip install -q -r requirements.txt
"$PY" -m app.seed
cd "$ROOT/frontend"
[ -d node_modules ] || npm install
npm run build
cd "$ROOT/backend"
echo "EcoByte running at http://localhost:8000  (admin@ecobyte.app / Admin@123, student@ecobyte.app / Student@123)"
"$PY" -m uvicorn app.main:app --port 8000
