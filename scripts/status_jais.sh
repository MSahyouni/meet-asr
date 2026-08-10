#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
echo "== env =="
grep -E '^(JAIS_|ULTRA_|SUM_|DOWNLOAD_|HF_HUB)' .env 2>/dev/null || true
echo "== model =="
du -sh data/models/summarizers/ultra/inceptionai_Jais-2-8B-Chat \
       data/models/summarizers/jais2/inceptionai_Jais-2-8B-Chat 2>/dev/null || echo missing
.venv/bin/python - <<'PY'
from pathlib import Path
import json
cands = [
    Path("data/models/summarizers/ultra/inceptionai_Jais-2-8B-Chat"),
    Path("data/models/summarizers/jais2/inceptionai_Jais-2-8B-Chat"),
]
root = next((p for p in cands if p.exists()), None)
if root is None:
    print("no_jais_dir")
    raise SystemExit
print("path", root)
idx = root / "model.safetensors.index.json"
if idx.exists():
    files = sorted(set(json.loads(idx.read_text())["weight_map"].values()))
    ok = [f for f in files if (root / f).exists() and (root / f).stat().st_size > 0]
    print(f"shards {len(ok)}/{len(files)}")
    for f in files:
        p = root / f
        print(f, "OK" if p.exists() else "MISS", f"{p.stat().st_size/1e9:.2f}G" if p.exists() else "")
incs = list(root.rglob("*.incomplete"))
print(f"incomplete={len(incs)} gb={sum(p.stat().st_size for p in incs)/1e9:.2f}")
PY
echo "== procs =="
pgrep -af 'huggingface-cli|hf download|smoke_summarize|download_jais2' || echo none
