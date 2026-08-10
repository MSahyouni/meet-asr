#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=apps/api
.venv/bin/python -m pytest tests/test_summarization_units.py -q --tb=short
.venv/bin/python - <<'PY'
from app.asr.whisper import unload_whisper_models
from app.nlp.rag import _FAISS_OK, faiss
print("unload_ok", unload_whisper_models())
print("faiss_ok", _FAISS_OK, faiss is not None)
PY
