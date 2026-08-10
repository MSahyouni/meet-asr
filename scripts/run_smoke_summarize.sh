#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=apps/api
mkdir -p data/outputs
# avoid pipe-to-tail buffering; write log directly
exec .venv/bin/python scripts/smoke_summarize_sample.py --mode jais > data/outputs/smoke_summarize.log 2>&1
