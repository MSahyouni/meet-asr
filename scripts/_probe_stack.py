#!/usr/bin/env python3
import pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
print("cwd ok", ROOT)

import torch, transformers
print("torch", torch.__version__, "cuda", torch.cuda.is_available())
print("transformers", transformers.__version__)
import torch.distributed.tensor as t
print("DTensor", hasattr(t, "DTensor"))

p = ROOT / "data/models/summarizers/ultra/inceptionai_Jais-2-8B-Chat"
shards = sorted(p.glob("model-*.safetensors"))
print("shards", len(shards), "dir_bytes", sum(f.stat().st_size for f in p.rglob("*") if f.is_file()))
for s in shards:
    print(" ", s.name, s.stat().st_size)
