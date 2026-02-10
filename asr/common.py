# asr/common.py — ثوابت وأدوات مشتركة
import os
import re
import pathlib
import tempfile
from typing import Optional, Dict

from config import settings

# يُستدعى بعد استيراد torch في asr/__init__
def setup_env(torch_module):
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
    os.environ.setdefault("CT2_USE_MMAP", "1")
    os.environ["SPEECHBRAIN_LOCAL_FILE_STRATEGY"] = "copy"
    os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    os.environ["HF_HOME"] = str(settings.HF_DIR)
    os.environ.pop("TRANSFORMERS_CACHE", None)
    os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(settings.HF_DIR))


def speaker_label(i: int) -> str:
    return f"متكلم_{i:02d}"


def to_ar_speaker(label: str) -> str:
    s = str(label or "").strip()
    if not s:
        return speaker_label(0)
    u = s.upper()
    if u.startswith("SPEAKER"):
        m = re.search(r"(\d+)$", u)
        if m:
            return speaker_label(int(m.group(1)))
        return speaker_label(0)
    if re.fullmatch(r"\d+", s):
        return speaker_label(int(s))
    return s


def err(msg: str) -> Dict:
    return {
        "text": "", "txt_path": None,
        "summary": "", "summary_path": None,
        "keywords": "", "segments": [],
        "srt_path": None, "vtt_path": None,
        "error": msg,
    }


def tmp_wav(suffix: str = ".wav") -> str:
    return tempfile.NamedTemporaryFile(prefix="asr_", suffix=suffix, delete=False).name


def safe_filename(p) -> str:
    try:
        base = pathlib.Path(str(p)).stem or "audio"
        return "".join(ch if (ch.isalnum() or ch in "-_.") else "_" for ch in base) or "audio"
    except Exception:
        return "audio"


def resolve_model(name: str) -> str:
    n = (name or "").strip().lower()
    return "large-v3" if n in ("heavy", "large-v3") else "medium"


def safe_compute(device: Optional[str], compute_type: Optional[str], has_cuda: bool):
    dev = (device or ("cuda" if has_cuda else "cpu")).lower()
    ctp = (compute_type or ("float16" if dev == "cuda" else "int8_float32")).lower()
    if dev != "cuda" and ctp == "float16":
        ctp = "int8_float32"
    return dev, ctp


# مسارات من الإعدادات (تُستخدم من الوحدات الأخرى)
OUTPUTS_DIR = settings.OUTPUTS_DIR
MODELS_DIR = settings.MODELS_DIR
SPK_DIR = settings.SPK_DIR
DEFAULT_MODEL = settings.WHISPER_MODEL
MODEL_CHOICES = ["light", "heavy"]
