# tests/conftest.py — pytest root and path
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ensure API package modules (under apps/api) are importable via namespace 'app'
API_DIR = os.path.join(ROOT, "apps", "api")
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

# --- Test-time env normalization (avoid deprecated cache var warning in transformers) ---
os.environ.pop("TRANSFORMERS_CACHE", None)
if not os.environ.get("HF_HOME"):
    os.environ["HF_HOME"] = os.path.join(ROOT, "data", "models")
