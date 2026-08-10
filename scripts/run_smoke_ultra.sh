#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data/outputs
LOG=data/outputs/smoke_ultra_result.log
echo "[run] $(date -Iseconds)" | tee "$LOG"
PYTHONPATH=apps/api .venv/bin/python scripts/smoke_summarize_sample.py --mode ultra 2>&1 | tee -a "$LOG"
echo "EXIT:$?" | tee -a "$LOG"
