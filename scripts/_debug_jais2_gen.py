#!/usr/bin/env python3
"""Debug why Jais-2 generate returns empty."""
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

from app.nlp.prompts import build_ultra_messages
from app.nlp.summarization import _load_ultra_pipe

sample = (ROOT / "scripts/sample_meeting_ar.txt").read_text(encoding="utf-8")[:500]
print("loading…")
pipe = _load_ultra_pipe()
tok = pipe.tokenizer
model = pipe.model
print("tok", type(tok).__name__)
print("eos", tok.eos_token, tok.eos_token_id, "pad", tok.pad_token, tok.pad_token_id)
print("bos", tok.bos_token, tok.bos_token_id)

messages = build_ultra_messages(sample, prompt_mode="meeting", stage="final")
inputs = tok.apply_chat_template(
    messages, add_generation_prompt=True, return_tensors="pt", return_dict=True
)
inputs = dict(inputs)
inputs.pop("token_type_ids", None)
print("input shape", inputs["input_ids"].shape, "last10", inputs["input_ids"][0, -10:].tolist())

import torch

device = next(p.device for p in model.parameters() if p.device.type != "meta")
inputs = {k: v.to(device) for k, v in inputs.items()}
suppress = [i for i in (tok.bos_token_id, 0) if i is not None]

try:
    with torch.inference_mode():
        out = model.generate(
            **inputs,
            max_new_tokens=64,
            do_sample=False,
            pad_token_id=tok.pad_token_id or tok.eos_token_id,
            eos_token_id=tok.eos_token_id,
            suppress_tokens=sorted(set(suppress)),
        )
    prompt_len = inputs["input_ids"].shape[-1]
    gen = out[0][prompt_len:]
    print("gen_len", int(gen.shape[0]), "gen_ids_head", gen[:20].tolist())
    print("decode_skip", repr(tok.decode(gen, skip_special_tokens=True)[:500]))
    print("decode_raw", repr(tok.decode(gen, skip_special_tokens=False)[:500]))
except Exception:
    traceback.print_exc()
