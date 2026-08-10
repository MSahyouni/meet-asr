#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys
import traceback

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except Exception:
    pass

P = ROOT / "data/models/summarizers/ultra/inceptionai_Jais-2-8B-Chat"
print("py files:", list(P.glob("*.py")))
print("has tokenizer.json", (P / "tokenizer.json").exists())

from app.infrastructure.torch_compat import ensure_dtensor_export

ensure_dtensor_export()

import transformers

print("transformers", transformers.__version__)

from transformers import AutoConfig, AutoTokenizer, AutoModelForCausalLM

try:
    c = AutoConfig.from_pretrained(P.as_posix(), trust_remote_code=True, local_files_only=True)
    print("config", type(c), c.model_type, getattr(c, "architectures", None), getattr(c, "auto_map", None))
except Exception:
    print("config FAILED")
    traceback.print_exc()

try:
    tok = AutoTokenizer.from_pretrained(
        P.as_posix(), trust_remote_code=True, use_fast=True, local_files_only=True
    )
    print("tok OK", type(tok), len(tok), tok.encode("مرحبا"))
except Exception:
    print("tok FAILED")
    traceback.print_exc()
    raise SystemExit(2)

try:
    m = AutoModelForCausalLM.from_config(c, trust_remote_code=True)
    print("from_config OK", type(m))
except Exception:
    print("from_config FAILED")
    traceback.print_exc()
