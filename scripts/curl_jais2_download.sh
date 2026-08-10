#!/usr/bin/env bash
# Robust Jais-2 download: .part + outer resume loop only (NO curl --retry).
# curl --retry + fixed -C offset was truncating progress back to the start offset.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a

TARGET="data/models/summarizers/ultra/inceptionai_Jais-2-8B-Chat"
LOG="data/outputs/jais2_download.log"
mkdir -p "$TARGET" data/outputs

echo "[fix] stop old downloaders"
pkill -f 'curl.*Jais-2-8B-Chat' 2>/dev/null || true
pkill -f 'download_jais2_shards.py' 2>/dev/null || true
tmux has-session -t jais2-dl 2>/dev/null && tmux kill-session -t jais2-dl || true
sleep 2

declare -A EXPECTED=(
  [model-00001-of-00004.safetensors]=4988455440
  [model-00002-of-00004.safetensors]=4963153816
  [model-00003-of-00004.safetensors]=4874521632
  [model-00004-of-00004.safetensors]=1354730176
)

.venv/bin/python - <<'PY' >>"$LOG" 2>&1 || true
import os
from pathlib import Path
from huggingface_hub import hf_hub_download
token=os.environ.get("HF_TOKEN")
root=Path("data/models/summarizers/ultra/inceptionai_Jais-2-8B-Chat")
for name in ["config.json","generation_config.json","tokenizer.json","tokenizer_config.json","special_tokens_map.json","model.safetensors.index.json","chat_template.jinja","README.md",".gitattributes"]:
    try:
        hf_hub_download(repo_id="inceptionai/Jais-2-8B-Chat", filename=name, local_dir=str(root), token=token)
        print("meta_ok", name, flush=True)
    except Exception as e:
        print("meta_skip", name, e, flush=True)
PY

for f in "${!EXPECTED[@]}"; do
  final="$TARGET/$f"
  part="$TARGET/$f.part"
  exp="${EXPECTED[$f]}"
  if [[ -f "$final" ]]; then
    sz=$(stat -c%s "$final")
    if [[ "$sz" -ge "$exp" ]]; then
      echo "[prep] complete $f ($sz)"
      rm -f "$part"
      continue
    fi
    psz=0
    [[ -f "$part" ]] && psz=$(stat -c%s "$part")
    if [[ "$sz" -gt "$psz" ]]; then
      echo "[prep] move incomplete $f ($sz) -> .part"
      mv -f "$final" "$part"
    else
      echo "[prep] drop smaller incomplete $f ($sz), keep .part ($psz)"
      rm -f "$final"
    fi
  fi
done

tmux new-session -d -s jais2-dl bash -lc '
set -uo pipefail
cd /home/mohamad/dev/meet-asr
set -a; source .env; set +a
TARGET=data/models/summarizers/ultra/inceptionai_Jais-2-8B-Chat
LOG=data/outputs/jais2_download.log

download_one() {
  local f="$1"
  local exp="$2"
  local final="$TARGET/$f"
  local part="$TARGET/$f.part"
  local url="https://huggingface.co/inceptionai/Jais-2-8B-Chat/resolve/main/$f"

  if [[ -f "$final" ]] && [[ "$(stat -c%s "$final")" -ge "$exp" ]]; then
    echo "[curl] skip $f already complete" | tee -a "$LOG"
    rm -f "$part"
    return 0
  fi

  local attempt=1
  while true; do
    local off=0
    [[ -f "$part" ]] && off=$(stat -c%s "$part")
    if [[ "$off" -ge "$exp" ]]; then
      break
    fi

    local before=$off
    echo "[curl] $(date -Is) $f attempt=$attempt resume_from=$off expect=$exp" | tee -a "$LOG"

    # -C - reads CURRENT size of -o file at start of THIS attempt only.
    # Do NOT pass curl --retry: it reuses the original offset and truncates.
    set +e
    curl -L \
      -C - \
      --connect-timeout 30 \
      --max-time 0 \
      -H "Authorization: Bearer $HF_TOKEN" \
      -o "$part" \
      "$url" >>"$LOG" 2>&1
    local rc=$?
    set -e

    off=0
    [[ -f "$part" ]] && off=$(stat -c%s "$part")
    echo "[curl] $f rc=$rc size_before=$before size_now=$off delta=$((off-before))" | tee -a "$LOG"

    if [[ "$off" -ge "$exp" ]]; then
      break
    fi
    if [[ "$off" -lt "$before" ]]; then
      echo "[curl] WARNING size shrank ($before -> $off); refusing truncate loss — restoring is N/A, continue from now" | tee -a "$LOG"
    fi

    attempt=$((attempt+1))
    if [[ "$attempt" -gt 80 ]]; then
      echo "[curl] FAIL giving up $f at $off" | tee -a "$LOG"
      return 1
    fi
    sleep 3
  done

  mv -f "$part" "$final"
  echo "[curl] ok $f size=$(stat -c%s "$final")" | tee -a "$LOG"
  return 0
}

download_one model-00001-of-00004.safetensors 4988455440
download_one model-00002-of-00004.safetensors 4963153816
download_one model-00003-of-00004.safetensors 4874521632
download_one model-00004-of-00004.safetensors 1354730176
echo "[dl] DONE curl $(date -Is)" | tee -a "$LOG"
'

echo "started: tmux attach -t jais2-dl"
sleep 6
ls -lh "$TARGET"/model-*.safetensors "$TARGET"/model-*.part 2>/dev/null || true
tail -n 12 "$LOG" | tr '\r' '\n' | tail -n 12
