# tts_xtts.py — غير مستخدم حاليًا (استُبدل بـ MMS-TTS و tts_arabic)
# XTTS v2 backend for Arabic (Coqui). Uses reference audio from data/voices/.
# لتفعيله: أضف استيراداً في tts_core وسكّن مسار MMS/tts_arabic.

import logging
import os
import pathlib

from config import settings

logger = logging.getLogger("tts_xtts")

TTS_XTTS_SAMPLE_RATE = 24000

# Arabic voices: ar_1 -> data/voices/1.wav, ar_2 -> 2.wav, ar_3 -> 3.wav
XTTS_ARABIC_VOICES = ["ar_1", "ar_2", "ar_3"]
XTTS_DEFAULT_ARABIC_VOICE = "ar_1"

_XTTS_MODEL = None


def _voice_id_to_speaker_wav(voice: str) -> pathlib.Path:
    """Map ar_1 -> 1.wav, ar_2 -> 2.wav, ar_3 -> 3.wav."""
    v = (voice or "").strip().lower()
    if v == "ar_1":
        return settings.SPK_DIR / "1.wav"
    if v == "ar_2":
        return settings.SPK_DIR / "2.wav"
    if v == "ar_3":
        return settings.SPK_DIR / "3.wav"
    # default
    return settings.SPK_DIR / "1.wav"


def _get_xtts():
    """Lazy-load XTTS model (singleton)."""
    global _XTTS_MODEL
    if _XTTS_MODEL is not None:
        return _XTTS_MODEL
    try:
        from TTS.api import TTS
        import torch
        use_gpu = torch.cuda.is_available()
        os.environ.setdefault("HF_HOME", str(settings.HF_DIR))
        os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(settings.HF_DIR / "hub"))
        logger.info("Loading XTTS-v2 for Arabic (first run may download ~1.7GB)...")
        _XTTS_MODEL = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=use_gpu)
        logger.info("XTTS-v2 loaded.")
        return _XTTS_MODEL
    except ImportError as e:
        raise RuntimeError(
            "XTTS requires 'coqui-tts'. Install with: pip install coqui-tts"
        ) from e
    except Exception as e:
        logger.exception("Failed to load XTTS: %s", e)
        raise RuntimeError(f"Failed to load XTTS: {e}") from e


def synthesize_xtts(
    text: str,
    voice: str = "",
    speed: float = 1.0,
    out_path: str = "",
) -> dict:
    """
    Synthesize Arabic text using XTTS-v2.
    voice: ar_1, ar_2, ar_3 (maps to 1.wav, 2.wav, 3.wav in data/voices/)
    """
    voice = (voice or "").strip() or XTTS_DEFAULT_ARABIC_VOICE
    speaker_wav = _voice_id_to_speaker_wav(voice)
    if not speaker_wav.exists():
        raise FileNotFoundError(
            f"XTTS reference audio not found: {speaker_wav}. "
            "Add 1.wav, 2.wav, 3.wav to data/voices/"
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
        "voice": voice,
    }


def list_xtts_voices() -> list:
    """Return XTTS Arabic voice IDs."""
    return list(XTTS_ARABIC_VOICES)
