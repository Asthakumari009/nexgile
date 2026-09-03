#!/usr/bin/env bash
# Starts all three servers. Ctrl-C stops everything.
set -euo pipefail
cd "$(dirname "$0")"

PY=.venv/Scripts/python.exe
[ -x "$PY" ] || PY=.venv/bin/python

trap 'kill 0' EXIT INT TERM

echo "backend  -> http://localhost:8000  (docs at /docs)"
(cd backend && "../$PY" -m uvicorn main:app --reload --port 8000) &

echo "internal -> http://localhost:5173  (React)"
(cd frontend && npm run dev -- --port 5173) &

echo "portal   -> http://localhost:4200  (Angular)"
(cd portal && npm start) &

wait
