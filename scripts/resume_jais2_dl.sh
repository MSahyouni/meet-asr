#!/usr/bin/env bash
# Resume Jais-2 download without hf_transfer (more reliable resume on flaky links).
set -euo pipefail
cd "$(dirname "$0")/.."
pkill -f 'huggingface-cli download inceptionai/Jais-2' 2>/dev/null || true
sleep 2
set -a
# shellcheck disable=SC1091
source .env
set +a
export HF_HUB_ENABLE_HF_TRANSFER=0
export DOWNLOAD_MAX_WORKERS="${DOWNLOAD_MAX_WORKERS:-8}"
export HF_TOKEN
TARGET="data/models/summarizers/ultra/inceptionai_Jais-2-8B-Chat"
LOG="data/outputs/jais2_download.log"
mkdir -p data/outputs
{
  echo "[dl] resume $(date -Is) workers=$DOWNLOAD_MAX_WORKERS hf_transfer=0"
} >>"$LOG"
nohup .venv/bin/huggingface-cli download inceptionai/Jais-2-8B-Chat \
  --local-dir "$TARGET" \
  --max-workers "$DOWNLOAD_MAX_WORKERS" \
  >>"$LOG" 2>&1 &
echo "pid=$!"
sleep 12
du -sh "$TARGET"
python3 - <<'PY'
from pathlib import Path
root = Path('data/models/summarizers/ultra/inceptionai_Jais-2-8B-Chat')
incs = list(root.rglob('*.incomplete'))
print(f'incomplete={len(incs)} mb={sum(p.stat().st_size for p in incs)/1e6:.0f}')
PY
tail -n 15 "$LOG"
