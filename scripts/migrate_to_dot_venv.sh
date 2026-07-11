#!/usr/bin/env bash
# Create .venv and install deps (migrate away from legacy venv/).
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"

if [[ -x "$root_dir/.venv/bin/python" ]]; then
  echo "[migrate] .venv already exists — nothing to do."
  exit 0
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "[migrate] python3 not found." >&2
  exit 1
fi

echo "[migrate] Creating .venv ..."
python3 -m venv "$root_dir/.venv"
"$root_dir/.venv/bin/python" -m pip install -U pip
"$root_dir/.venv/bin/python" -m pip install -r "$root_dir/apps/api/requirements.txt"

if [[ -x "$root_dir/venv/bin/pip" ]]; then
  echo "[migrate] Optional: reinstall extras from old venv if needed, e.g.:"
  echo "  .venv/bin/pip install mishkal habibi-tts"
  echo "[migrate] After verifying ./run.sh works, you may remove the old env:"
  echo "  rm -rf venv"
fi

echo "[migrate] Done. Run: ./run.sh"
