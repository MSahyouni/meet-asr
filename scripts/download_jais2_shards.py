#!/usr/bin/env python3
"""Download Jais-2 shards one-by-one with resume + clear progress logging."""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT / "apps" / "api" / ".env", override=False)
except Exception:
    pass

os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"

from huggingface_hub import hf_hub_download, list_repo_files

REPO = "inceptionai/Jais-2-8B-Chat"
TARGET = ROOT / "data" / "models" / "summarizers" / "ultra" / "inceptionai_Jais-2-8B-Chat"
LOG = ROOT / "data" / "outputs" / "jais2_download.log"
TOKEN = (os.environ.get("HF_TOKEN") or "").strip() or None

WEIGHT_EXTS = (".safetensors", ".bin", ".gguf", ".pt", ".ckpt")


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def main() -> int:
    TARGET.mkdir(parents=True, exist_ok=True)
    log(f"start repo={REPO} target={TARGET} token={'yes' if TOKEN else 'no'}")
    try:
        files = list_repo_files(REPO, token=TOKEN)
    except Exception as e:
        log(f"list_repo_files failed: {e}")
        return 2

    # Prefer weight shards first, then the rest
    weights = [f for f in files if f.endswith(WEIGHT_EXTS)]
    others = [f for f in files if f not in weights]
    ordered = weights + others
    log(f"files={len(ordered)} weights={len(weights)}")

    for i, name in enumerate(ordered, 1):
        dest = TARGET / name
        if dest.exists() and dest.stat().st_size > 0 and not name.endswith(".incomplete"):
            # For sharded index, existence of final file is enough
            if not str(dest).endswith(".incomplete"):
                log(f"[{i}/{len(ordered)}] skip existing {name} ({dest.stat().st_size/1e9:.2f}G)")
                continue
        for attempt in range(1, 8):
            try:
                log(f"[{i}/{len(ordered)}] download {name} attempt={attempt}")
                path = hf_hub_download(
                    repo_id=REPO,
                    filename=name,
                    local_dir=str(TARGET),
                    token=TOKEN,
                    force_download=False,
                )
                size = Path(path).stat().st_size if Path(path).exists() else 0
                log(f"[{i}/{len(ordered)}] ok {name} ({size/1e9:.2f}G)")
                break
            except Exception as e:
                log(f"[{i}/{len(ordered)}] fail {name}: {e}")
                if attempt >= 7:
                    log("giving up on file")
                    log(traceback.format_exc())
                    return 1
                time.sleep(min(60, 5 * attempt))

    # Completeness check
    idx = TARGET / "model.safetensors.index.json"
    if idx.exists():
        shards = sorted(set(json.loads(idx.read_text(encoding="utf-8")).get("weight_map", {}).values()))
        missing = [s for s in shards if not (TARGET / s).exists()]
        if missing:
            log(f"incomplete missing_shards={missing}")
            return 1
        log(f"complete shards={len(shards)}")
    else:
        log("warning: no model.safetensors.index.json")
    log("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
