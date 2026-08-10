#!/usr/bin/env bash
# Keep Jais-2 download alive inside tmux (survives terminal close).
# Token is loaded inside the session from .env — never put on argv.
set -euo pipefail
cd "$(dirname "$0")/.."
SESSION=jais2-dl
pkill -f 'download_jais2_shards.py' 2>/dev/null || true
sleep 1
tmux has-session -t "$SESSION" 2>/dev/null && tmux kill-session -t "$SESSION"
tmux new-session -d -s "$SESSION" bash -lc '
  cd /home/mohamad/dev/meet-asr
  set -a
  source .env
  set +a
  export HF_HUB_ENABLE_HF_TRANSFER=0
  exec .venv/bin/python -u scripts/download_jais2_shards.py 2>&1 | tee -a data/outputs/jais2_download.log
'
echo "tmux session: $SESSION"
echo "attach: tmux attach -t $SESSION"
sleep 2
tmux ls
pgrep -af download_jais2_shards | sed 's/hf_[A-Za-z0-9]*/hf_REDACTED/g' || echo 'not running'
