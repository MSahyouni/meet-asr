#!/usr/bin/env bash
# Fix stack for Jais-2: need torch with DTensor + transformers that knows jais2.
set -euo pipefail
cd "$(dirname "$0")/.."
LOG=data/outputs/jais2_stack_fix.log
mkdir -p data/outputs
exec > >(tee "$LOG") 2>&1

echo "=== probe before ==="
.venv/bin/python - <<'PY'
import torch
print("torch", torch.__version__)
import torch.distributed.tensor as t
print("tensor file", getattr(t, "__file__", None))
print("has DTensor", hasattr(t, "DTensor"))
try:
    from torch.distributed._tensor import DTensor
    print("_tensor.DTensor OK", DTensor)
except Exception as e:
    print("_tensor.DTensor FAIL", e)
PY

echo "=== upgrade torch/torchaudio to 2.5.1+cu124 ==="
.venv/bin/pip install --index-url https://download.pytorch.org/whl/cu124 \
  'torch==2.5.1' 'torchaudio==2.5.1'

echo "=== probe after ==="
.venv/bin/python - <<'PY'
import torch
print("torch", torch.__version__, "cuda", torch.cuda.is_available())
import torch.distributed.tensor as t
print("has DTensor", hasattr(t, "DTensor"), getattr(t, "DTensor", None))
PY

echo "=== jais2 arch ==="
PYTHONPATH=apps/api .venv/bin/python scripts/_debug_jais2_arch.py || true
echo "=== DONE ==="
