#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
bash scripts/status_ultra.sh
python3 - <<'PY'
from pathlib import Path
import time
r = Path("data/models/summarizers/ultra/inceptionai_Jais-2-8B-Chat")

def tot():
    return sum(p.stat().st_size for p in r.rglob("*.incomplete"))

a = tot()
time.sleep(20)
b = tot()
print(f"grow_MB={(b-a)/1e6:.1f} in 20s  now_GB={b/1e9:.2f}")
PY
tail -n 10 data/outputs/jais2_download.log
