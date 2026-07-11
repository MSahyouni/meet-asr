#!/usr/bin/env bash
# Pre-download OmniVoice weights into data/models (resumable, shared retry policy).
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"

export HF_HOME="$root_dir/data/models"
export HF_HUB_DISABLE_SYMLINKS=1
export HF_HUB_ENABLE_HF_TRANSFER=0
export HF_HUB_DOWNLOAD_TIMEOUT="${HF_HUB_DOWNLOAD_TIMEOUT:-120}"

if ! getent hosts huggingface.co >/dev/null 2>&1; then
  echo "[download_omnivoice] DNS error: cannot resolve huggingface.co" >&2
  echo "Fix WSL DNS first:" >&2
  echo "  sudo ./scripts/fix_wsl_dns.sh" >&2
  echo "  wsl --shutdown   # from Windows PowerShell, then reopen Ubuntu" >&2
  exit 2
fi

venv_py="$root_dir/.venv/bin/python"
if [[ ! -x "$venv_py" ]]; then
  venv_py="$root_dir/venv/bin/python"
fi
if [[ ! -x "$venv_py" ]]; then
  echo "[download_omnivoice] API venv not found. Run ./run.sh once to create .venv" >&2
  exit 1
fi

# OmniVoice CLI still lives in a separate venv (inference only).
omnivoice_py="$root_dir/.tools/omnivoice/.venv/bin/python"
if [[ ! -x "$omnivoice_py" ]]; then
  echo "[download_omnivoice] Creating OmniVoice inference venv..."
  mkdir -p "$root_dir/.tools/omnivoice"
  python3 -m venv "$root_dir/.tools/omnivoice/.venv"
  "$root_dir/.tools/omnivoice/.venv/bin/python" -m pip install -U pip omnivoice
fi

echo "[download_omnivoice] Downloading k2-fsa/OmniVoice into $HF_HOME ..."
echo "[download_omnivoice] This is ~3.2GB and may take a while."
echo "[download_omnivoice] Safe to interrupt (Ctrl+C) and re-run — download resumes from saved bytes."
echo "[download_omnivoice] Uses shared download_retry policy (same as Whisper/NLP)."

(
  cd "$root_dir/apps/api"
  PYTHONPATH="$root_dir/apps/api" "$venv_py" -m app.infrastructure.omnivoice_download "$@"
)

if [[ $? -eq 0 ]]; then
  echo "[download_omnivoice] Done. OmniVoice weights are ready."
fi
echo "[download_omnivoice] Check size with:"
echo "  du -sb data/models/hub/models--k2-fsa--OmniVoice data/models/models--k2-fsa--OmniVoice"
