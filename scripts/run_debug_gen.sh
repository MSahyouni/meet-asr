#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data/outputs
PYTHONPATH=apps/api .venv/bin/python scripts/_debug_jais2_gen.py 2>&1 | tee data/outputs/jais2_gen_debug.log
