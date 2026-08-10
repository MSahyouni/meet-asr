"""Smoke-test Jais-2 meeting summarization on a sample Arabic transcript.

Loads .env from repo root / apps/api. First run may download Jais-2 (~minutes).

  PYTHONPATH=apps/api .venv/bin/python scripts/smoke_summarize_sample.py
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sample",
        default=str(ROOT / "scripts" / "sample_meeting_ar.txt"),
    )
    parser.add_argument("--mode", default="jais", help="ignored except off; Jais-2 only")
    args = parser.parse_args()

    sys.path.insert(0, str(ROOT / "apps" / "api"))
    from app.config import settings
    from app.nlp.summarization import summarize

    sample_path = Path(args.sample)
    text = sample_path.read_text(encoding="utf-8")
    print(f"[smoke] sample={sample_path} chars={len(text)}")
    print(f"[smoke] jais_model={settings.JAIS_MODEL} prompt={settings.JAIS_PROMPT_MODE}")
    t0 = time.perf_counter()
    summary, keywords = summarize(text, mode=args.mode)
    dt = time.perf_counter() - t0
    print(f"[smoke] done in {dt:.1f}s")
    print("--- summary ---")
    print(summary or "(empty)")
    print("--- keywords ---")
    print(keywords or "(none)")
    return 0 if (summary or "").strip() else 1


if __name__ == "__main__":
    raise SystemExit(main())
