#!/usr/bin/env bash
set -euo pipefail

# Launch pattern reference:
# DISPLAY=:99 google-chrome-stable --remote-debugging-port=9222 --user-data-dir=/root/.browser-login/google-chrome-user-data --no-sandbox

DISPLAY_NUM="${DISPLAY_NUM:-99}"
DISPLAY=":${DISPLAY_NUM}"
SCREEN_GEOMETRY="${SCREEN_GEOMETRY:-1600x1000x24}"
CHROME_PORT="${CHROME_PORT:-9222}"
CHROME_ADDR="${CHROME_ADDR:-127.0.0.1}"
USER_DATA_DIR="${USER_DATA_DIR:-/root/.browser-login/google-chrome-user-data}"
START_URL="${START_URL:-https://notebooklm.google.com/}"
XVFB_LOG="${XVFB_LOG:-/var/log/notebooklm-xvfb.log}"
CHROME_LOG="${CHROME_LOG:-/var/log/notebooklm-chrome.log}"

install -d -m 0700 "${USER_DATA_DIR}"

if ! pgrep -af "Xvfb ${DISPLAY}" >/dev/null 2>&1; then
  nohup Xvfb "${DISPLAY}" -screen 0 "${SCREEN_GEOMETRY}" >"${XVFB_LOG}" 2>&1 &
  sleep 1
fi

if ! curl -fsS "http://${CHROME_ADDR}:${CHROME_PORT}/json/version" >/dev/null 2>&1; then
  nohup env DISPLAY="${DISPLAY}" google-chrome-stable \
    --remote-debugging-address="${CHROME_ADDR}" \
    --remote-debugging-port="${CHROME_PORT}" \
    --user-data-dir="${USER_DATA_DIR}" \
    --no-sandbox \
    --new-window \
    "${START_URL}" >"${CHROME_LOG}" 2>&1 &
fi

for _ in $(seq 1 30); do
  if curl -fsS "http://${CHROME_ADDR}:${CHROME_PORT}/json/version" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

curl -fsS "http://${CHROME_ADDR}:${CHROME_PORT}/json/version" | jq .
