#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
from pathlib import Path
keys = [
    "ULTRA_MODEL","ULTRA_PROMPT_MODE","ULTRA_4BIT","ULTRA_TRUST_REMOTE","ULTRA_ALLOW_DOWNLOAD",
    "SUM_RELEASE_ASR_GPU","SUM_MAX_INPUT_TOKENS","SUM_MAX_PARTS","DOWNLOAD_MAX_WORKERS","HF_HUB_ENABLE_HF_TRANSFER",
]
root = {}
for line in Path(".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        root[k.strip()] = v.strip()
api = Path("apps/api/.env")
lines = api.read_text(encoding="utf-8").splitlines() if api.exists() else []
out, seen = [], set()
for line in lines:
    if "=" in line and not line.strip().startswith("#"):
        k = line.split("=", 1)[0].strip()
        if k in keys and k in root:
            out.append(f"{k}={root[k]}")
            seen.add(k)
            continue
    out.append(line)
for k in keys:
    if k in root and k not in seen:
        out.append(f"{k}={root[k]}")
api.write_text("\n".join(out) + "\n", encoding="utf-8")
print("synced apps/api/.env")
PY
chmod +x scripts/start_jais2_download.sh scripts/status_ultra.sh scripts/stop_jais_downloads.sh
bash scripts/start_jais2_download.sh
sleep 25
bash scripts/status_ultra.sh
echo "== log =="
tail -n 25 data/outputs/jais2_download.log || true
