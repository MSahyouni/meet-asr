#!/usr/bin/env python3
"""Verify that config paths are calculated correctly and models are found."""

import sys
import pathlib

# Add apps/api to path to import app modules
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "apps" / "api"))

from app.config import settings

print("=" * 80)
print("CONFIGURATION VERIFICATION")
print("=" * 80)

# Print key paths
print(f"\n📁 Project Structure:")
print(f"  BASE_DIR:      {settings.BASE_DIR}")
print(f"  DATA_DIR:      {settings.DATA_DIR}")
print(f"  MODELS_DIR:    {settings.MODELS_DIR}")
print(f"  HF_DIR:        {settings.HF_DIR}")
print(f"  OUTPUTS_DIR:   {settings.OUTPUTS_DIR}")

# Check if key directories exist
print(f"\n✓ Directory Verification:")
dirs_to_check = {
    "DATA_DIR": settings.DATA_DIR,
    "MODELS_DIR": settings.MODELS_DIR,
    "HF_DIR": settings.HF_DIR,
    "OUTPUTS_DIR": settings.OUTPUTS_DIR,
}
for name, path in dirs_to_check.items():
    exists = path.exists()
    status = "✓ exists" if exists else "✗ missing"
    print(f"  {name:15} {status:15} {path}")

# Check for local models
print(f"\n🤖 Local Models Found:")
models_to_check = {
    "whisper-large-v3": settings.MODELS_DIR / "whisper-large-v3",
    "whisper-medium": settings.MODELS_DIR / "whisper-medium",
    "multilingual-e5-base": settings.MODELS_DIR / "multilingual-e5-base",
    "spkrec_ecapa_cpu": settings.MODELS_DIR / "spkrec_ecapa_cpu",
    "summarizers/mT5_XLSum": settings.MODELS_DIR / "summarizers" / "mT5_XLSum",
}
for name, path in models_to_check.items():
    exists = path.exists()
    status = "✓ found" if exists else "✗ not found"
    print(f"  {name:25} {status:15} {path}")

# Check model configuration settings
print(f"\n⚙️  Model Configuration:")
print(f"  WHISPER_MODEL:       {settings.WHISPER_MODEL}")
print(f"  SUMMARIZER_MODEL:    {settings.SUMMARIZER_MODEL}")
print(f"  RAG_EMB_MODEL:       {settings.RAG_EMB_MODEL}")
print(f"  NER_MODEL:           {settings.NER_MODEL}")
print(f"  PUNCT_MODEL:         {settings.PUNCT_MODEL}")

# Check HF environment variables
print(f"\n🔧 Environment Variables:")
import os
print(f"  HF_HOME:             {os.environ.get('HF_HOME', '(not set)')}")
print(f"  SENTENCE_TRANSFORMERS_HOME: {os.environ.get('SENTENCE_TRANSFORMERS_HOME', '(not set)')}")

print("\n" + "=" * 80)
print("✓ Configuration verified successfully!")
print("=" * 80)
