#!/usr/bin/env bash
# Fix intermittent DNS failures in WSL (PEP 668 / Hugging Face downloads).
# Run inside WSL: sudo ./scripts/fix_wsl_dns.sh
set -euo pipefail

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run with sudo: sudo ./scripts/fix_wsl_dns.sh" >&2
  exit 1
fi

echo "[fix_wsl_dns] Setting /etc/resolv.conf ..."
rm -f /etc/resolv.conf
cat >/etc/resolv.conf <<'EOF'
nameserver 1.1.1.1
nameserver 8.8.8.8
options timeout:2 attempts:3 rotate
EOF
chmod 644 /etc/resolv.conf

echo "[fix_wsl_dns] Configuring /etc/wsl.conf (generateResolvConf=false) ..."
mkdir -p /etc
if [[ -f /etc/wsl.conf ]]; then
  cp /etc/wsl.conf /etc/wsl.conf.bak."$(date +%Y%m%d%H%M%S)"
fi

python3 - <<'PY'
from pathlib import Path

path = Path("/etc/wsl.conf")
lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
out = []
in_network = False
seen_generate = False
seen_network = False

for line in lines:
    stripped = line.strip()
    if stripped == "[network]":
        in_network = True
        seen_network = True
        out.append(line)
        continue
    if stripped.startswith("[") and stripped != "[network]":
        in_network = False
    if in_network and stripped.startswith("generateResolvConf"):
        out.append("generateResolvConf=false")
        seen_generate = True
        continue
    out.append(line)

if not seen_network:
    out.append("")
    out.append("[network]")
if not seen_generate:
    out.append("generateResolvConf=false")

path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
PY

echo "[fix_wsl_dns] Testing DNS ..."
if getent hosts huggingface.co >/dev/null 2>&1; then
  echo "[fix_wsl_dns] OK: huggingface.co resolves."
  getent hosts huggingface.co | head -n 1
else
  echo "[fix_wsl_dns] WARNING: huggingface.co still not resolving." >&2
  echo "Close WSL completely from PowerShell: wsl --shutdown" >&2
  echo "Then reopen Ubuntu and run: getent hosts huggingface.co" >&2
  exit 2
fi

echo "[fix_wsl_dns] Done. If DNS breaks again after reboot, run: wsl --shutdown then reopen Ubuntu."
