# tts_xtts.py — غير مستخدم حاليًا (استُبدل بـ MMS-TTS و tts_arabic)
# XTTS v2 backend for Arabic (Coqui). Uses reference audio from data/voices/.
# لتفعيله: أضف استيراداً في tts_core وسكّن مسار MMS/tts_arabic.

import logging
import os
import pathlib
from typing import Optional

from app.config import settings
from app.tts.voice_profiles import resolve_user_speaker_path, list_user_speaker_samples

logger = logging.getLogger("tts_xtts")

TTS_XTTS_SAMPLE_RATE = 24000

XTTS_DEFAULT_SPEAKER_REF = "voice.wav"

_XTTS_MODEL = None


def _ensure_transformers_compat() -> None:
    """Patch missing helpers expected by coqui-tts on older transformers builds."""
    try:
        from transformers.utils import import_utils as _import_utils
        patched = False

        if not hasattr(_import_utils, "is_torch_greater_or_equal"):
            from packaging import version
            import torch

            def _is_torch_greater_or_equal(target_version: str) -> bool:
                try:
                    current = str(torch.__version__).split("+")[0]
                    return version.parse(current) >= version.parse(str(target_version))
                except Exception:
                    return False

            _import_utils.is_torch_greater_or_equal = _is_torch_greater_or_equal
            patched = True

        if not hasattr(_import_utils, "is_torchcodec_available"):
            def _is_torchcodec_available() -> bool:
                return False

            _import_utils.is_torchcodec_available = _is_torchcodec_available
            patched = True

        if patched:
            logger.info("Applied XTTS compatibility patch for transformers import_utils")
    except Exception as e:
        logger.debug("Transformers compatibility patch skipped: %s", e)

def _get_xtts():
    """Lazy-load XTTS model (singleton)."""
    global _XTTS_MODEL
    if _XTTS_MODEL is not None:
        return _XTTS_MODEL
    try:
        _ensure_transformers_compat()
        from TTS.api import TTS
        import torch
        use_gpu = torch.cuda.is_available()
        os.environ.setdefault("HF_HOME", str(settings.HF_DIR))
        os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(settings.HF_DIR / "hub"))
        os.environ.setdefault("TTS_HOME", str(settings.HF_DIR / "coqui_tts"))
        logger.info("Loading XTTS-v2 for Arabic (first run may download ~1.7GB)...")
        _XTTS_MODEL = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=use_gpu)
        logger.info("XTTS-v2 loaded.")
        return _XTTS_MODEL
    except ImportError as e:
        raise RuntimeError(
            f"XTTS import failed: {e}. Install/repair with: pip install -U coqui-tts"
        ) from e
    except Exception as e:
        logger.exception("Failed to load XTTS: %s", e)
        raise RuntimeError(f"Failed to load XTTS: {e}") from e


def synthesize_xtts(
    text: str,
    voice: str = "",
    speed: float = 1.0,
    out_path: str = "",
    user_email: Optional[str] = None,
    speaker_ref: Optional[str] = None,
) -> dict:
    """
    Synthesize text using XTTS-v2 and a user-specific speaker sample.
    user_email: required user key for per-user speaker folder under data/voices/<user>/
    speaker_ref: filename inside the user's voice folder (default: voice.wav)
    """
    if not (user_email or "").strip():
        raise ValueError("XTTS requires user_email to select the user's voice folder")
    speaker_wav = resolve_user_speaker_path(user_email=user_email, speaker_ref=speaker_ref)
    if not speaker_wav.exists():
        available = [p.name for p in list_user_speaker_samples(user_email)]
        available_txt = ", ".join(available[:8]) if available else "none"
        raise FileNotFoundError(
            f"XTTS speaker sample not found: {speaker_wav}. "
            f"Available samples: {available_txt}. "
            "Upload a sample first using POST /tts/voice-sample"
        )

    out_dir = pathlib.Path(settings.OUTPUTS_DIR) / "tts"
    out_dir.mkdir(parents=True, exist_ok=True)
    if not out_path or not pathlib.Path(out_path).suffix:
        import time
        base = f"xtts_{int(time.time() * 1000)}"
        out_path = str(out_dir / f"{base}.wav")
    else:
        p = pathlib.Path(out_path)
        if not p.is_absolute():
            p = out_dir / p.name
        p.parent.mkdir(parents=True, exist_ok=True)
        out_path = str(p.resolve())

    tts = _get_xtts()
    # XTTS tts_to_file: text, file_path, speaker_wav, language
    # speed: Coqui uses speed multiplier
    tts.tts_to_file(
        text=text,
        file_path=out_path,
        speaker_wav=str(speaker_wav),
        language="ar",
    )

    import soundfile as sf
    info = sf.info(out_path)
    duration_sec = info.duration
    sample_rate = info.samplerate

    return {
        "audio_path": out_path,
        "sample_rate": sample_rate,
        "duration_sec": round(duration_sec, 3),
        "voice": voice or "xtts",
        "speaker_ref": speaker_wav.name,
    }


def list_xtts_voices() -> list:
    """Return XTTS mode label."""
    return ["xtts"]
