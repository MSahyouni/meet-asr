#!/usr/bin/env bash
# Diagnose + restart Jais download via aria2c (multi-connection) or curl.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a
export HF_HUB_ENABLE_HF_TRANSFER=0

TARGET="data/models/summarizers/ultra/inceptionai_Jais-2-8B-Chat"
LOG="data/outputs/jais2_download.log"
mkdir -p "$TARGET" data/outputs

echo "[fix] killing stuck downloaders..."
pkill -f 'download_jais2_shards.py' 2>/dev/null || true
tmux has-session -t jais2-dl 2>/dev/null && tmux kill-session -t jais2-dl || true
sleep 1

echo "[fix] quick network probe..."
curl -sI -m 15 https://huggingface.co | head -n 3 || echo "hf_head_fail"
# Small file first
code=$(curl -s -o /tmp/jais_cfg.json -w '%{http_code}' -m 30 \
  -H "Authorization: Bearer ${HF_TOKEN}" \
  "https://huggingface.co/inceptionai/Jais-2-8B-Chat/resolve/main/config.json" || true)
echo "config_http=$code"

echo "[fix] 20s speed probe on smallest shard (00004)..."
rm -f /tmp/jais_probe.bin
curl -L -m 25 -C - -o /tmp/jais_probe.bin \
  -H "Authorization: Bearer ${HF_TOKEN}" \
  -w "http=%{http_code} bytes=%{size_download} speed=%{speed_download}\n" \
  "https://huggingface.co/inceptionai/Jais-2-8B-Chat/resolve/main/model-00004-of-00004.safetensors" \
  || true
ls -lh /tmp/jais_probe.bin 2>/dev/null || true

# Prefer aria2c if available
if command -v aria2c >/dev/null 2>&1; then
  echo "[fix] using aria2c multi-connection download"
  SHARDS=(
    model-00001-of-00004.safetensors
    model-00002-of-00004.safetensors
    model-00003-of-00004.safetensors
    model-00004-of-00004.safetensors
  )
  # Also fetch metadata files first via python quickly
  .venv/bin/python - <<'PY'
from huggingface_hub import hf_hub_download
import os
from pathlib import Path
token=os.environ.get("HF_TOKEN")
root=Path("data/models/summarizers/ultra/inceptionai_Jais-2-8B-Chat")
for name in ["config.json","generation_config.json","tokenizer.json","tokenizer_config.json","special_tokens_map.json","model.safetensors.index.json","chat_template.jinja","README.md",".gitattributes"]:
    try:
        hf_hub_download(repo_id="inceptionai/Jais-2-8B-Chat", filename=name, local_dir=str(root), token=token)
        print("meta_ok", name)
    except Exception as e:
        print("meta_skip", name, e)
PY
  {
    echo "[dl] $(date -Is) aria2c start"
  } >>"$LOG"
  tmux new-session -d -s jais2-dl bash -lc "
    cd /home/mohamad/dev/meet-asr
    set -a; source .env; set +a
    for f in model-00001-of-00004.safetensors model-00002-of-00004.safetensors model-00003-of-00004.safetensors model-00004-of-00004.safetensors; do
      echo \"[aria2] \$f\" | tee -a data/outputs/jais2_download.log
      aria2c -c -x 8 -s 8 -k 1M \
        --header=\"Authorization: Bearer \$HF_TOKEN\" \
        -d data/models/summarizers/ultra/inceptionai_Jais-2-8B-Chat \
        -o \"\$f\" \
        \"https://huggingface.co/inceptionai/Jais-2-8B-Chat/resolve/main/\$f\" \
        >> data/outputs/jais2_download.log 2>&1 || echo \"[aria2] fail \$f\" | tee -a data/outputs/jais2_download.log
    done
    echo '[dl] DONE aria2' | tee -a data/outputs/jais2_download.log
  "
  echo "started tmux jais2-dl with aria2c"
else
  echo "[fix] aria2c missing — installing..."
  sudo apt-get update -qq && sudo apt-get install -y -qq aria2
  exec bash "$0"
fi

sleep 8
du -sh "$TARGET"
tail -n 20 "$LOG"
tmux ls
