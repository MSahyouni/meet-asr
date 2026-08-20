# asr/common.py — ثوابت وأدوات مشتركة
import os
import re
import pathlib
import tempfile
from typing import Optional, Dict

from app.config import settings

# يُستدعى بعد استيراد torch في asr/__init__
def setup_env(torch_module):
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
    os.environ.setdefault("CT2_USE_MMAP", "1")
    os.environ["SPEECHBRAIN_LOCAL_FILE_STRATEGY"] = "copy"
    os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    # Prefer standard resumable HTTP downloads over Xet for large local model pulls.
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    os.environ["HF_HOME"] = str(settings.HF_DIR)
    os.environ.pop("TRANSFORMERS_CACHE", None)
    os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(settings.HF_DIR))


def speaker_label(i: int) -> str:
    return f"متكلم_{i:02d}"


def speaker_id_from_label(label: str) -> str:
    """معرّف تقني ثابت للمتكلم داخل الجلسة (spk_00, spk_01, ...)."""
    s = str(label or "").strip()
    if not s:
        return "spk_00"
    u = s.upper()
    if u.startswith("SPK_"):
        m = re.search(r"(\d+)$", u)
        if m:
            return f"spk_{int(m.group(1)):02d}"
        return "spk_00"
    if u.startswith("SPEAKER"):
        m = re.search(r"(\d+)$", u)
        if m:
            return f"spk_{int(m.group(1)):02d}"
        return "spk_00"
    if s.startswith("متكلم"):
        m = re.search(r"(\d+)$", s)
        if m:
            return f"spk_{int(m.group(1)):02d}"
        return "spk_00"
    if re.fullmatch(r"\d+", s):
        return f"spk_{int(s):02d}"
    # اسم مسجّل أو تسمية أخرى — لا تُحوَّل إلى رقم؛ تبقى مرتبطة عبر speaker_id الأصلي إن وُجد
    slug = re.sub(r"[^\w\u0600-\u06FF]+", "_", s, flags=re.UNICODE).strip("_")
    return f"spk_{slug[:40]}" if slug else "spk_00"


def to_ar_speaker(label: str) -> str:
    s = str(label or "").strip()
    if not s:
        return speaker_label(0)
    u = s.upper()
    if u.startswith("SPEAKER") or u.startswith("SPK_"):
        m = re.search(r"(\d+)$", u)
        if m:
            return speaker_label(int(m.group(1)))
        return speaker_label(0)
    if re.fullmatch(r"\d+", s):
        return speaker_label(int(s))
    return s


def format_speaker_display(seg: Dict) -> str:
    """تسمية العرض مع المعرّف الثابت إن وُجد."""
    name = to_ar_speaker(seg.get("speaker", ""))
    sid = str(seg.get("speaker_id") or "").strip()
    if not sid:
        sid = speaker_id_from_label(seg.get("speaker", ""))
    if sid and sid not in name:
        return f"{name} [{sid}]"
    return name


def ensure_segment_speaker_id(seg: Dict) -> Dict:
    """اضمن وجود speaker_id على المقطع دون المساس بالاسم المعروض."""
    if not str(seg.get("speaker_id") or "").strip():
        seg["speaker_id"] = speaker_id_from_label(seg.get("speaker", ""))
    return seg


def err(msg: str) -> Dict:
    return {
        "text": "", "txt_path": None, "docx_path": None,
        "summary": "", "summary_path": None, "summary_docx_path": None,
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
    """Map UI/env model names to faster-whisper size ids.

    light -> base (fast)
    medium -> medium
    heavy / large / large-v3 -> large-v3 (best multilingual quality)
    """
    n = (name or "").strip().lower()
    if n in ("heavy", "large", "large-v3", "large_v3"):
        return "large-v3"
    if n in ("medium",):
        return "medium"
    if n in ("light", "base", "small", "tiny"):
        # Keep light→base; allow explicit small/tiny if requested later
        return {"light": "base", "base": "base", "small": "small", "tiny": "tiny"}.get(n, "base")
    # Prefer quality over accidentally falling back to base
    return "large-v3"


def safe_compute(device: Optional[str], compute_type: Optional[str], has_cuda: bool):
    """Resolve device/compute, treating 'auto' as unset (use settings / sensible defaults)."""
    raw_dev = (device or "").strip().lower()
    raw_ctp = (compute_type or "").strip().lower()
    if raw_dev in ("", "auto"):
        configured = (getattr(settings, "WHISPER_DEVICE", "") or "").strip().lower()
        if configured in ("cuda", "cpu"):
            raw_dev = configured
        else:
            raw_dev = "cuda" if has_cuda else "cpu"
    if raw_dev == "cuda" and not has_cuda:
        raw_dev = "cpu"

    if raw_ctp in ("", "auto"):
        configured_ctp = (getattr(settings, "WHISPER_COMPUTE", "") or "").strip().lower()
        if configured_ctp:
            raw_ctp = configured_ctp
        else:
            # int8 fits large-v3 on 6–8GB laptop GPUs; float16 often OOMs.
            raw_ctp = "int8" if raw_dev == "cuda" else "int8_float32"

    if raw_dev != "cuda" and raw_ctp in ("float16", "int8"):
        if raw_ctp == "float16":
            raw_ctp = "int8_float32"
        elif raw_ctp == "int8":
            raw_ctp = "int8_float32"
    return raw_dev, raw_ctp


# مسارات من الإعدادات (تُستخدم من الوحدات الأخرى)
OUTPUTS_DIR = settings.OUTPUTS_DIR
MODELS_DIR = settings.MODELS_DIR
SPK_DIR = settings.SPK_DIR
DEFAULT_MODEL = settings.WHISPER_MODEL
MODEL_CHOICES = ["heavy"]
