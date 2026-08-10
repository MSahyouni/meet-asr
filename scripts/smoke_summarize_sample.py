#!/usr/bin/env python3
"""Smoke-test meeting summarization (ultra/lite) on a sample Arabic transcript.

Loads .env from repo root / apps/api. First ultra run may download Jais-2 (~minutes).

  cd /home/mohamad/dev/meet-asr
  PYTHONPATH=apps/api .venv/bin/python scripts/smoke_summarize_sample.py
  PYTHONPATH=apps/api .venv/bin/python scripts/smoke_summarize_sample.py --mode lite
"""
from __future__ import annotations

import argparse
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
API = ROOT / "apps" / "api"
sys.path.insert(0, str(API))

# Load env before importing settings-backed modules
try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    load_dotenv(API / ".env")
except Exception:
    pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test Arabic meeting summarization")
    parser.add_argument("--mode", default="ultra", choices=("ultra",))
    parser.add_argument(
        "--file",
        default=str(ROOT / "scripts" / "sample_meeting_ar.txt"),
        help="UTF-8 transcript path",
    )
    args = parser.parse_args()

    text = pathlib.Path(args.file).read_text(encoding="utf-8")
    print(f"[smoke] mode={args.mode} chars={len(text)}")
    print(f"[smoke] ULTRA_MODEL will follow apps/api Settings / env")

    from app.config import settings
    from app.nlp.summarization import summarize
    from app.nlp.text_utils import get_summary_source

    print(f"[smoke] ultra_model={settings.ULTRA_MODEL} prompt={settings.ULTRA_PROMPT_MODE}")
    t0 = time.time()
    summary, keywords = summarize(text, mode=args.mode)
    dt = time.time() - t0

    print("--- summary ---")
    print(summary or "(empty)")
    print("--- keywords ---")
    print(keywords or "(none)")
    print(f"--- source={get_summary_source()} elapsed={dt:.1f}s ---")
    return 0 if (summary or "").strip() else 1


if __name__ == "__main__":
    raise SystemExit(main())
