#!/usr/bin/env bash
# Reliable background download for Jais-2-8B-Chat (resume-friendly, no hf_transfer).
set -euo pipefail
cd "$(dirname "$0")/.."
pkill -f 'huggingface-cli download inceptionai/Jais-2' 2>/dev/null || true
pkill -f 'hf download inceptionai/Jais-2' 2>/dev/null || true
sleep 1
set -a
# shellcheck disable=SC1091
source .env
set +a
export HF_HUB_ENABLE_HF_TRANSFER=0
export HF_TOKEN
WORKERS="${DOWNLOAD_MAX_WORKERS:-8}"
TARGET="data/models/summarizers/ultra/inceptionai_Jais-2-8B-Chat"
LOG="data/outputs/jais2_download.log"
mkdir -p data/outputs "$TARGET"
{
  echo "[dl] $(date -Is) start workers=$WORKERS model=inceptionai/Jais-2-8B-Chat"
} >>"$LOG"

# Prefer new `hf` CLI when available
if [[ -x .venv/bin/hf ]]; then
  DL=(.venv/bin/hf download)
else
  DL=(.venv/bin/huggingface-cli download)
fi

nohup "${DL[@]}" inceptionai/Jais-2-8B-Chat \
  --local-dir "$TARGET" \
  --max-workers "$WORKERS" \
  >>"$LOG" 2>&1 &
echo "pid=$! log=$LOG"
