#!/usr/bin/env python3
"""Check HF access to Jais-2 without printing the full token."""
from __future__ import annotations

import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT / "apps" / "api" / ".env")
except Exception:
    pass

token = (os.environ.get("HF_TOKEN") or "").strip()
print(f"token_present={bool(token)} token_len={len(token)}")

from huggingface_hub import HfApi, hf_hub_download

api = HfApi(token=token or None)
try:
    info = api.whoami()
    print(f"whoami={info.get('name')}")
except Exception as e:
    print(f"whoami_failed={type(e).__name__}: {e}")
    sys.exit(2)

try:
    path = hf_hub_download(
        repo_id="inceptionai/Jais-2-8B-Chat",
        filename="README.md",
        token=token or None,
    )
    print(f"jais2_access=ok path={path}")
except Exception as e:
    print(f"jais2_access=failed {type(e).__name__}: {str(e)[:400]}")
    sys.exit(1)

sys.exit(0)
