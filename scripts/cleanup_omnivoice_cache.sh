#!/usr/bin/env bash
# Remove orphan .incomplete blobs after OmniVoice snapshot is complete.
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"

export HF_HOME="$root_dir/data/models"

venv_py="$root_dir/.venv/bin/python"
if [[ ! -x "$venv_py" ]]; then
  venv_py="$root_dir/venv/bin/python"
fi
if [[ ! -x "$venv_py" ]]; then
  echo "[cleanup_omnivoice_cache] API venv not found. Run ./run.sh first." >&2
  exit 1
fi

(
  cd "$root_dir/apps/api"
  PYTHONPATH="$root_dir/apps/api" "$venv_py" -m app.infrastructure.omnivoice_download --cleanup-only
)
