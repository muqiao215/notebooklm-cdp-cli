#!/usr/bin/env bash
set -euo pipefail

DISPLAY_NUM="${DISPLAY_NUM:-99}"
DISPLAY=":${DISPLAY_NUM}"
CHROME_ADDR="${CHROME_ADDR:-127.0.0.1}"
CHROME_PORT="${CHROME_PORT:-9222}"
REPO_DIR="${REPO_DIR:-$(pwd)}"
UV_BIN="${UV_BIN:-$HOME/.local/bin/uv}"

echo "[1/5] display and cdp"
pgrep -af "Xvfb ${DISPLAY}"
curl -fsS "http://${CHROME_ADDR}:${CHROME_PORT}/json/version" | jq .
curl -fsS "http://${CHROME_ADDR}:${CHROME_PORT}/json/list" | jq 'map({title,url})'

echo "[2/5] listeners"
ss -ltnp | grep -E "(:${CHROME_PORT}|:5901|:6080)" || true

if [[ ! -d "${REPO_DIR}" ]]; then
  echo "Repository not found: ${REPO_DIR}" >&2
  exit 1
fi

if [[ ! -x "${UV_BIN}" ]]; then
  UV_BIN="$(command -v uv)"
fi

cd "${REPO_DIR}"

echo "[3/5] uv sync"
"${UV_BIN}" sync

echo "[4/5] doctor path"
"${UV_BIN}" run notebooklm --host "${CHROME_ADDR}" --port "${CHROME_PORT}" browser status --json
"${UV_BIN}" run notebooklm --host "${CHROME_ADDR}" --port "${CHROME_PORT}" doctor --json
"${UV_BIN}" run notebooklm --host "${CHROME_ADDR}" --port "${CHROME_PORT}" auth check --json

echo "[5/5] notebook access"
"${UV_BIN}" run notebooklm --host "${CHROME_ADDR}" --port "${CHROME_PORT}" notebook list --json
