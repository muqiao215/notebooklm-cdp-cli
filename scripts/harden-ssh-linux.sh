#!/usr/bin/env bash
set -euo pipefail

AUTHORIZED_KEYS="${SSH_AUTHORIZED_KEYS:-$HOME/.ssh/authorized_keys}"

if [[ ! -s "${AUTHORIZED_KEYS}" ]]; then
  echo "Refusing to continue: ${AUTHORIZED_KEYS} is missing or empty." >&2
  exit 1
fi

install -d -m 0755 /etc/fail2ban/jail.d
cat >/etc/fail2ban/jail.d/sshd.local <<'EOF'
[sshd]
enabled = true
backend = systemd
port = ssh
maxretry = 5
findtime = 10m
bantime = 1h
EOF

install -d -m 0755 /etc/ssh/sshd_config.d
cat >/etc/ssh/sshd_config.d/99-root-key-only.conf <<'EOF'
PermitRootLogin prohibit-password
PasswordAuthentication no
KbdInteractiveAuthentication no
ChallengeResponseAuthentication no
PubkeyAuthentication yes
EOF

systemctl enable --now fail2ban
sshd -t
systemctl reload ssh || systemctl reload sshd
