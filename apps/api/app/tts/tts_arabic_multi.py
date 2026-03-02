# tts_arabic_multi.py — Multi-voice Arabic TTS via nipponjo/tts_arabic (4 speakers)
"""Offline Arabic TTS with 4 voices. Optional: pip install git+https://github.com/nipponjo/tts_arabic.git"""

import logging
import pathlib
from app.config import settings

logger = logging.getLogger("tts_arabic_multi")

# ar_1 -> speaker 0, ar_2 -> 1, ar_3 -> 2, ar_4 -> 3
ARABIC_MULTI_VOICES = ["ar_1", "ar_2", "ar_3", "ar_4"]

# Profiles to make voices feel more different (pace + pitch)
VOICE_PROFILES = {
    # مرجعية: صوت افتراضي متوازن
    "ar_1": {"pace": 1.0, "pitch_mul": 1.0, "pitch_add": 0.0},
    # صوت أعلى وأسرع قليلاً
    "ar_2": {"pace": 1.15, "pitch_mul": 1.1, "pitch_add": 1.0},
    # صوت أعمق وأبطأ قليلاً
    "ar_3": {"pace": 0.9, "pitch_mul": 0.9, "pitch_add": -1.0},
    # صوت أعمق وبطيء أكثر (رزين)
    "ar_4": {"pace": 0.8, "pitch_mul": 0.85, "pitch_add": -2.0},
}


def _voice_to_speaker_id(voice: str) -> int:
    v = (voice or "").strip().lower()
    if v == "ar_1":
        return 0
    if v == "ar_2":
        return 1
    if v == "ar_3":
        return 2
    if v == "ar_4":
        return 3
    return 0


def synthesize_arabic_multi(
    text: str,
    voice: str = "ar_1",
    speed: float = 1.0,
    out_path: str = "",
) -> dict:
    """
    Synthesize Arabic with tts_arabic (4 speakers).
    voice: ar_1, ar_2, ar_3, ar_4.
    """
    try:
        from tts_arabic import tts as tts_arabic_fn
    except ImportError as e:
        raise RuntimeError(
            "Multi-voice Arabic TTS requires tts_arabic. Install: pip install git+https://github.com/nipponjo/tts_arabic.git"
        ) from e

    speaker_id = _voice_to_speaker_id(voice)
    out_dir = pathlib.Path(settings.OUTPUTS_DIR) / "tts"
    out_dir.mkdir(parents=True, exist_ok=True)
    if not out_path or not pathlib.Path(out_path).suffix:
        import time
        base = f"ar_{int(time.time() * 1000)}"
        out_path = str(out_dir / f"{base}.wav")
    else:
        p = pathlib.Path(out_path)
        if not p.is_absolute():
            p = out_dir / p.name
        p.parent.mkdir(parents=True, exist_ok=True)
        out_path = str(p.resolve())

    # pace + pitch per voice so they sound more distinct
    voice_key = (voice or "ar_1").strip().lower()
    profile = VOICE_PROFILES.get(voice_key, VOICE_PROFILES["ar_1"])
    # pace: 1.0 = normal; نضربها في speed القادم من الـ API
    speed_clamped = max(0.5, min(2.0, float(speed)))
    pace = max(0.5, min(2.0, profile["pace"] * speed_clamped))

    wave = tts_arabic_fn(
        text,
        speaker=speaker_id,
        pace=pace,
        pitch_mul=profile["pitch_mul"],
        pitch_add=profile["pitch_add"],
        save_to=out_path,
        play=False,
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


def is_available() -> bool:
    try:
        from tts_arabic import tts  # noqa: F401
        return True
    except ImportError:
        return False
