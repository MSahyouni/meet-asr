#!/usr/bin/env bash
# Fast resume download for Jais-2-8B-Chat (8 workers + hf_transfer when available).
# Uses HF_TOKEN from environment / .env — do not pass token on argv.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a
# shellcheck disable=SC1091
source .env
set +a
export HF_HUB_ENABLE_HF_TRANSFER="${HF_HUB_ENABLE_HF_TRANSFER:-1}"
export DOWNLOAD_MAX_WORKERS="${DOWNLOAD_MAX_WORKERS:-8}"
export HF_TOKEN
mkdir -p data/outputs data/models/summarizers/ultra
TARGET="data/models/summarizers/ultra/inceptionai_Jais-2-8B-Chat"
LOG="data/outputs/jais2_download.log"
echo "[dl] starting -> $TARGET (workers=$DOWNLOAD_MAX_WORKERS)" | tee "$LOG"
exec .venv/bin/huggingface-cli download inceptionai/Jais-2-8B-Chat \
  --local-dir "$TARGET" \
  --max-workers "$DOWNLOAD_MAX_WORKERS" \
  >>"$LOG" 2>&1
