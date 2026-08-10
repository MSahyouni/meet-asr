#!/usr/bin/env python3
"""One-off: print full traceback for ultra model load failure."""
from __future__ import annotations

import pathlib
import re
import sys
import traceback

ROOT = pathlib.Path(__file__).resolve().parents[1]
API = ROOT / "apps" / "api"
sys.path.insert(0, str(API))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    load_dotenv(API / ".env")
except Exception:
    pass

from app.config import settings
from app.nlp.models_loader import ensure_local, _looks_like_complete_model_dir

print("ULTRA_MODEL", settings.ULTRA_MODEL)
print("ULTRA_4BIT", settings.ULTRA_4BIT)
print("MODELS_DIR", settings.MODELS_DIR)
print("HF_TOKEN set", bool(settings.HF_TOKEN))

ultra_subdir = "summarizers/ultra/" + re.sub(r"[^A-Za-z0-9._-]+", "_", settings.ULTRA_MODEL.strip())
target = (settings.MODELS_DIR / ultra_subdir).resolve()
print("target", target)
print("complete", _looks_like_complete_model_dir(target))
if target.exists():
    for p in sorted(target.iterdir()):
        if p.is_file():
            print(f"  {p.name}\t{p.stat().st_size}")

try:
    local_path = ensure_local(settings.ULTRA_MODEL, ultra_subdir, allow_download=False)
    print("ensure_local OK", local_path)
except Exception:
    print("ensure_local FAILED")
    traceback.print_exc()
    raise SystemExit(1)

from transformers import AutoTokenizer, AutoModelForCausalLM

try:
    tok = AutoTokenizer.from_pretrained(
        local_path,
        token=settings.HF_TOKEN,
        trust_remote_code=settings.ULTRA_TRUST_REMOTE,
        use_fast=False,
    )
    print("tokenizer OK", type(tok).__name__)
except Exception:
    print("tokenizer FAILED")
    traceback.print_exc()
    raise SystemExit(2)

if settings.ULTRA_4BIT:
    try:
        import torch
        from transformers import BitsAndBytesConfig

        print("cuda", torch.cuda.is_available())
        bnb_cfg = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.float16,
        )
        model = AutoModelForCausalLM.from_pretrained(
            local_path,
            token=settings.HF_TOKEN,
            trust_remote_code=settings.ULTRA_TRUST_REMOTE,
            quantization_config=bnb_cfg,
            device_map="auto",
        )
        print("4bit model OK", type(model).__name__)
    except Exception:
        print("4bit FAILED")
        traceback.print_exc()
        raise SystemExit(3)
else:
    print("ULTRA_4BIT=0, skipping 4bit path")

print("DONE")
