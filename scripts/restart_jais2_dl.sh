#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
pkill -f 'huggingface-cli download inceptionai/Jais-2' 2>/dev/null || true
sleep 1
nohup ./scripts/download_jais2.sh >/dev/null 2>&1 &
echo "restarted pid=$!"
sleep 20
du -sh data/models/summarizers/ultra/inceptionai_Jais-2-8B-Chat || true
python3 - <<'PY'
from pathlib import Path
root = Path('data/models/summarizers/ultra/inceptionai_Jais-2-8B-Chat')
incs = list(root.rglob('*.incomplete'))
total = sum(p.stat().st_size for p in incs)
print(f'incomplete_files={len(incs)} incomplete_mb={total/1024/1024:.1f}')
PY
tail -n 15 data/outputs/jais2_download.log || true
pgrep -af 'huggingface-cli download' | sed 's/hf_[A-Za-z0-9]*/hf_REDACTED/g' || true
