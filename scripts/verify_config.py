#!/usr/bin/env python3
"""Verify that config paths are calculated correctly and models are found."""

import os
import sys
import pathlib

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "apps" / "api"))

from app.config import settings

print("=" * 80)
print("CONFIGURATION VERIFICATION")
print("=" * 80)

print(f"\nProject Structure:")
print(f"  BASE_DIR:      {settings.BASE_DIR}")
print(f"  DATA_DIR:      {settings.DATA_DIR}")
print(f"  MODELS_DIR:    {settings.MODELS_DIR}")
print(f"  HF_DIR:        {settings.HF_DIR}")
print(f"  OUTPUTS_DIR:   {settings.OUTPUTS_DIR}")

print(f"\nDirectory Verification:")
dirs_to_check = {
    "DATA_DIR": settings.DATA_DIR,
    "MODELS_DIR": settings.MODELS_DIR,
    "HF_DIR": settings.HF_DIR,
    "OUTPUTS_DIR": settings.OUTPUTS_DIR,
}
for name, path in dirs_to_check.items():
    status = "exists" if path.exists() else "missing"
    print(f"  {name:15} {status:15} {path}")

print(f"\nLocal Models Found:")
slug = "".join(c if c.isalnum() or c in "._-" else "_" for c in settings.JAIS_MODEL.strip())
models_to_check = {
    "whisper-large-v3": settings.MODELS_DIR / "whisper-large-v3",
    f"jais2 ({slug})": settings.MODELS_DIR / "summarizers" / "ultra" / slug,
    "jais2 alt path": settings.MODELS_DIR / "summarizers" / "jais2" / slug,
    "punctuation": settings.MODELS_DIR / "punctuation" / "arabic_punct",
    "spkrec_ecapa_cpu": settings.MODELS_DIR / "spkrec_ecapa_cpu",
}
for name, path in models_to_check.items():
    status = "found" if path.exists() else "not found"
    print(f"  {name:28} {status:12} {path}")

print(f"\nModel Configuration:")
print(f"  WHISPER_MODEL:       {settings.WHISPER_MODEL}")
print(f"  JAIS_MODEL:          {settings.JAIS_MODEL}")
print(f"  JAIS_4BIT:           {settings.JAIS_4BIT}")
print(f"  JAIS_PROMPT_MODE:    {settings.JAIS_PROMPT_MODE}")
print(f"  RAG_EMB_MODEL:       {settings.RAG_EMB_MODEL}")
print(f"  NER_MODEL:           {settings.NER_MODEL}")
print(f"  PUNCT_MODEL:         {settings.PUNCT_MODEL}")

print(f"\nEnvironment Variables:")
print(f"  HF_HOME:             {os.environ.get('HF_HOME', '(not set)')}")
print(f"  SENTENCE_TRANSFORMERS_HOME: {os.environ.get('SENTENCE_TRANSFORMERS_HOME', '(not set)')}")

print("\n" + "=" * 80)
print("Configuration verified.")
print("=" * 80)
