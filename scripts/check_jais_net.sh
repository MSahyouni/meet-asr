#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a
echo "== process =="
pgrep -af 'huggingface-cli download' || echo none
echo "== network sample =="
ss -tp 2>/dev/null | grep -E 'huggingface|python' | head -n 10 || true
echo "== curl hf =="
curl -sI -m 15 https://huggingface.co | head -n 5 || echo curl_hf_fail
echo "== curl model config =="
code=$(curl -s -o /tmp/jais_cfg.json -w '%{http_code}' -m 30 \
  -H "Authorization: Bearer $HF_TOKEN" \
  https://huggingface.co/inceptionai/Jais-2-8B-Chat/resolve/main/config.json || true)
echo "http=$code bytes=$(wc -c </tmp/jais_cfg.json 2>/dev/null || echo 0)"
echo "== incomplete =="
python3 - <<'PY'
from pathlib import Path
root=Path('data/models/summarizers/ultra/inceptionai_Jais-2-8B-Chat')
for p in sorted(root.rglob('*.incomplete')):
    print(f'{p.stat().st_size/1e6:8.1f} MB  {p.name[-40:]}')
PY
