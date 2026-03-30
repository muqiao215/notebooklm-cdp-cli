# Linux Server Runbook

This runbook documents the validated Linux-first deployment path for `notebooklm-cdp-cli`.

## Scope

This path assumes:

- Ubuntu or Debian family host
- root shell available
- one persistent Chrome profile on the server
- CDP bound to `127.0.0.1:9222`
- login recovery handled through the same profile via noVNC

This runbook does not use:

- browser extensions
- `storage_state.json`
- `auth import-browser`
- public CDP exposure

## 1. Install base packages

Use the bundled script:

```bash
ssh root@<host> 'bash -s' < scripts/install-base-linux.sh
```

Or install manually:

```bash
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  xvfb \
  x11vnc \
  novnc \
  websockify \
  ca-certificates \
  curl \
  fail2ban \
  gnupg \
  jq \
  git \
  python3-pip \
  python3-venv
```

## 2. Start Chrome under Xvfb

Use the bundled script:

```bash
ssh root@<host> 'bash -s' < scripts/start-chrome-cdp-linux.sh
```

The key launch pattern is:

```bash
DISPLAY=:99 google-chrome-stable \
  --remote-debugging-address=127.0.0.1 \
  --remote-debugging-port=9222 \
  --user-data-dir=/root/.browser-login/google-chrome-user-data \
  --no-sandbox
```

Validate:

```bash
curl -fsS http://127.0.0.1:9222/json/version | jq .
curl -fsS http://127.0.0.1:9222/json/list | jq 'map({title,url})'
```

Important observation: fixed-port attach worked reliably in the validated flow even when `DevToolsActivePort` did not exist. Prefer explicit host and port over auto-discovery.

## 3. Start noVNC handoff

Use the bundled script:

```bash
ssh root@<host> 'bash -s' < scripts/start-novnc-linux.sh
```

Then tunnel from the local machine:

```bash
ssh -N -L 26080:127.0.0.1:6080 root@<host>
```

Open:

```text
http://127.0.0.1:26080/vnc.html?autoconnect=true&resize=remote&view_only=0
```

If Google login is required, complete it there so the same server-side Chrome profile becomes authenticated.

## 4. Clone and verify the repo

```bash
mkdir -p /root/work
git clone https://github.com/muqiao215/notebooklm-cdp-cli.git /root/work/notebooklm-cdp-cli
cd /root/work/notebooklm-cdp-cli
~/.local/bin/uv sync
```

Use the bundled verification script:

```bash
ssh root@<host> 'REPO_DIR=/root/work/notebooklm-cdp-cli bash -s' < scripts/verify-linux-host.sh
```

Or run the key commands directly:

```bash
uv run notebooklm --host 127.0.0.1 --port 9222 browser status --json
uv run notebooklm --host 127.0.0.1 --port 9222 doctor --json
uv run notebooklm --host 127.0.0.1 --port 9222 auth check --json
uv run notebooklm --host 127.0.0.1 --port 9222 notebook list --json
```

## 5. Harden SSH after key access is proven

Use the bundled script:

```bash
ssh root@<host> 'bash -s' < scripts/harden-ssh-linux.sh
```

This installs `fail2ban`, configures the `sshd` jail with `backend = systemd`, and switches root SSH to public-key-only authentication.

Do not run it before verifying that key login already works.
