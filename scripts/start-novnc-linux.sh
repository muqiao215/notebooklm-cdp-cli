#!/usr/bin/env bash
set -euo pipefail

DISPLAY_NUM="${DISPLAY_NUM:-99}"
DISPLAY=":${DISPLAY_NUM}"
VNC_ADDR="${VNC_ADDR:-127.0.0.1}"
VNC_PORT="${VNC_PORT:-5901}"
NOVNC_ADDR="${NOVNC_ADDR:-127.0.0.1}"
NOVNC_PORT="${NOVNC_PORT:-6080}"
VNC_LOG="${VNC_LOG:-/var/log/notebooklm-x11vnc.log}"
NOVNC_LOG="${NOVNC_LOG:-/var/log/notebooklm-novnc.log}"
NOVNC_WEB_ROOT="${NOVNC_WEB_ROOT:-/usr/share/novnc}"

if ! pgrep -af "x11vnc.*${VNC_PORT}" >/dev/null 2>&1; then
  nohup x11vnc \
    -display "${DISPLAY}" \
    -listen "${VNC_ADDR}" \
    -rfbport "${VNC_PORT}" \
    -forever \
    -shared \
    -nopw >"${VNC_LOG}" 2>&1 &
  sleep 1
fi

if ! pgrep -af "(novnc_proxy|websockify).*(^| )${NOVNC_PORT}( |$)" >/dev/null 2>&1; then
  if [[ -x /usr/share/novnc/utils/novnc_proxy ]]; then
    nohup /usr/share/novnc/utils/novnc_proxy \
      --listen "${NOVNC_ADDR}:${NOVNC_PORT}" \
      --vnc "${VNC_ADDR}:${VNC_PORT}" >"${NOVNC_LOG}" 2>&1 &
  else
    nohup websockify \
      --web "${NOVNC_WEB_ROOT}" \
      "${NOVNC_ADDR}:${NOVNC_PORT}" \
      "${VNC_ADDR}:${VNC_PORT}" >"${NOVNC_LOG}" 2>&1 &
  fi
fi

cat <<EOF
noVNC handoff ready.
Tunnel:
  ssh -N -L 26080:${NOVNC_ADDR}:${NOVNC_PORT} root@<host>
Open:
  http://127.0.0.1:26080/vnc.html?autoconnect=true&resize=remote&view_only=0
EOF
