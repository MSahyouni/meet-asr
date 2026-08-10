#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
pkill -f 'download_jais2_shards.py' 2>/dev/null || true
pkill -f 'huggingface-cli download inceptionai/Jais-2' 2>/dev/null || true
pkill -f 'hf download inceptionai/Jais-2' 2>/dev/null || true
sleep 1
set -a
# shellcheck disable=SC1091
source .env
set +a
export HF_HUB_ENABLE_HF_TRANSFER=0
export HF_TOKEN
mkdir -p data/outputs
# setsid detaches fully from terminal/WSL session quirks
setsid .venv/bin/python -u scripts/download_jais2_shards.py \
  >>data/outputs/jais2_download.log 2>&1 < /dev/null &
echo "pid=$!"
sleep 3
pgrep -af download_jais2_shards || echo 'not running'
tail -n 15 data/outputs/jais2_download.log || true
