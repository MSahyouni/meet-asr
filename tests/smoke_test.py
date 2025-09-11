import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import importlib

def test_imports():
    for mod in ["faster_whisper", "gradio", "torch", "librosa", "soundfile", "resampy", "noisereduce", "sklearn", "huggingface_hub", "speechbrain"]:
        importlib.import_module(mod)

def test_api_health_route_import():
    # مجرد تحقق أن api.py قابل للاستيراد
    import api
    assert hasattr(api, "app")
