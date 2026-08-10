# tts_core.py — TTS: Habibi فقط (استنساخ لهجة + بصمة صوت)
import logging
import pathlib
from functools import lru_cache
from typing import Optional

from app.config import settings

logger = logging.getLogger("tts_core")


@lru_cache(maxsize=512)
def _preprocess_text_cached(text: str) -> str:
    from app.tts.text_utils import preprocess_for_tts
    return preprocess_for_tts(text, normalize=True, numbers=True, punctuation=True)


def _preprocess_text(text: str) -> str:
    """Apply Arabic preprocessing (normalize, numbers, punctuation) before TTS."""
    if not getattr(settings, "TTS_PREPROCESS_ENABLED", True):
        return text
    try:
        return _preprocess_text_cached(text)
    except ImportError:
        return text


def maybe_diacritize(text: str, enabled: Optional[bool] = None) -> str:
    """
    Optional Arabic diacritics (تشكيل) — kept for API compatibility.
    Habibi strips tashkeel internally; prefer leaving this off.
    """
    use = bool(enabled) if enabled is not None else bool(getattr(settings, "TTS_DIACRITIZE", False))
    if not use:
        return text
    try:
        from app.tts.diacritize import add_diacritics
        return add_diacritics(text)
    except ImportError:
        return text


TTS_TEXT_MAX_LEN = 5000
TTS_SPEED_MIN = 0.25
TTS_SPEED_MAX = 2.0
TTS_DEFAULT_VOICE = "habibi_unified"
TTS_ALLOWED_ENGINES = {"auto", "habibi"}
TTS_REMOVED_ENGINES = {"xtts", "xtts_v2", "mms", "omnivoice"}

TTS_KNOWN_VOICES = [
    "habibi_unified",
    "habibi_specialized",
]

TTS_VOICE_ENGINE = {
    "habibi_unified": "habibi",
    "habibi_specialized": "habibi",
}


def _resolve_user_speaker_ref_if_available(user_email: Optional[str], speaker_ref: Optional[str]) -> Optional[str]:
    if not (user_email or "").strip():
        return None
    try:
        from app.tts.voice_profiles import resolve_user_speaker_path

        candidate = resolve_user_speaker_path(user_email=user_email, speaker_ref=speaker_ref)
        if candidate.exists() and candidate.is_file():
            return candidate.name
    except Exception:
        return None
    return None


def _format_habibi_runtime_error(exc: Exception) -> str:
    raw = str(exc) or exc.__class__.__name__
    lowered = raw.lower()
    network_markers = (
        "failed to resolve",
        "getaddrinfo failed",
        "max retries exceeded",
        "read timed out",
        "connection timed out",
        "httpsconnectionpool",
        "huggingface.co",
    )
    if any(marker in lowered for marker in network_markers):
        return (
            "فشل تنزيل نموذج Habibi بسبب شبكة/DNS مع Hugging Face. "
            "تحقق من الاتصال ثم أعد المحاولة (التنزيل يُستكمل تلقائياً). "
            f"Original error: {raw}"
        )
    return f"Habibi failed: {raw}"


def _habibi_model_choice(requested_voice: str) -> str:
    voice = (requested_voice or "").strip().lower()
    if voice in ("habibi_unified", "habibi_specialized"):
        return voice
    # توافق قديم: أي صوت غير معروف → الموحّد
    return "habibi_unified"


def _normalize_engine(engine: str) -> str:
    e = (engine or "habibi").strip().lower() or "habibi"
    if e in TTS_REMOVED_ENGINES:
        raise ValueError(
            f"محرك {e} أُزيل من المشروع. استخدم engine=habibi مع بصمة صوت و ref_text."
        )
    if e == "auto":
        return "habibi"
    if e not in TTS_ALLOWED_ENGINES:
        raise ValueError(f"engine must be one of: {', '.join(sorted(TTS_ALLOWED_ENGINES))}")
    return e


class TTSCore:
    """Habibi فقط: لهجات عربية + استنساخ بصمة (يتطلب عينة صوت + ref_text)."""

    def __init__(self, lang_code: Optional[str] = None):
        self.lang_code = (lang_code or "ar").strip() or "ar"

    def synthesize(
        self,
        text: str,
        voice: str = "",
        speed: float = 1.0,
        out_path: str = "",
        seed: Optional[int] = None,
        engine: str = "habibi",
        user_email: Optional[str] = None,
        speaker_ref: Optional[str] = None,
        ref_text: Optional[str] = None,
        dialect: Optional[str] = None,
        diacritize: Optional[bool] = None,
        max_chunk_chars: Optional[int] = None,
    ) -> dict:
        text = (text or "").strip()
        if not text:
            raise ValueError("Text cannot be empty.")
        if len(text) > TTS_TEXT_MAX_LEN:
            raise ValueError(
                f"Text length ({len(text)}) exceeds maximum ({TTS_TEXT_MAX_LEN} characters)."
            )

        try:
            speed_f = float(speed)
        except (TypeError, ValueError):
            raise ValueError(f"Speed must be a number between {TTS_SPEED_MIN} and {TTS_SPEED_MAX}.")
        if not (TTS_SPEED_MIN <= speed_f <= TTS_SPEED_MAX):
            raise ValueError(
                f"Speed must be between {TTS_SPEED_MIN} and {TTS_SPEED_MAX}, got {speed_f}."
            )
        speed = speed_f
        _ = seed  # ignored (Habibi-only)
        _ = diacritize  # Habibi strips tashkeel; ignore mishkal

        engine_requested = _normalize_engine(engine)
        requested_voice = (voice or "").strip() or TTS_DEFAULT_VOICE
        text_h = _preprocess_text(text)

        if not (user_email or "").strip():
            raise ValueError("Habibi requires user_email and uploaded voice sample")

        from app.tts.voice_profiles import get_user_speaker_ref_text, resolve_user_speaker_path
        from app.tts.tts_habibi import synthesize_habibi

        habibi_speaker_ref = _resolve_user_speaker_ref_if_available(
            user_email=user_email, speaker_ref=speaker_ref
        )
        try:
            ref_audio = resolve_user_speaker_path(
                user_email=user_email,
                speaker_ref=habibi_speaker_ref or speaker_ref,
            )
        except Exception as e:
            raise ValueError(f"Habibi requires an uploaded voice sample: {e}") from e

        resolved_ref_text = (
            (ref_text or "").strip()
            or get_user_speaker_ref_text(user_email, ref_audio.name)
            or ""
        ).strip()
        if not resolved_ref_text:
            raise ValueError(
                "Habibi requires ref_text matching the voice sample only "
                "(not the full text to generate). Add it in the form or when uploading the sample."
            )

        requested_model = _habibi_model_choice(requested_voice)
        try:
            result = synthesize_habibi(
                text=text_h,
                ref_audio_path=str(ref_audio),
                ref_text=resolved_ref_text,
                speed=speed,
                out_path=out_path,
                model_choice=requested_model,
                dialect=dialect or "UNK",
                max_chunk_chars=max_chunk_chars,
            )
        except (ImportError, RuntimeError, FileNotFoundError, ValueError) as e:
            raise ValueError(f"Habibi failed: {e}") from e
        except Exception as e:
            logger.exception("Habibi runtime error: %s", e)
            raise RuntimeError(_format_habibi_runtime_error(e)) from e

        result.update({
            "engine_used": "habibi",
            "arabic_detected": True,
            "fallback_used": False,
            "requested_voice": requested_voice,
            "resolved_voice": result.get("voice", requested_model),
            "speaker_ref": ref_audio.name,
            "dialect": result.get("dialect", (dialect or "UNK").upper()),
            "diacritize": False,
            "max_chunk_chars": max_chunk_chars,
            "engine_requested": engine_requested,
        })
        return result


def list_voices() -> list:
    return list(TTS_KNOWN_VOICES)


def _engine_status_habibi() -> dict:
    try:
        import importlib.util

        if importlib.util.find_spec("habibi_tts") is None:
            return {
                "engine": "habibi",
                "ready": False,
                "status": "habibi-tts غير مثبت (pip install habibi-tts)",
            }
        return {"engine": "habibi", "ready": True, "status": "جاهز (الحزمة متوفرة)"}
    except Exception as e:
        return {"engine": "habibi", "ready": False, "status": str(e)}


def list_engine_status() -> list[dict]:
    return [_engine_status_habibi()]


def list_voices_detailed() -> list[dict]:
    by_engine = {item["engine"]: item for item in list_engine_status()}
    detailed = []
    for voice_id in TTS_KNOWN_VOICES:
        engine = TTS_VOICE_ENGINE.get(voice_id, "habibi")
        info = by_engine.get(engine) or {}
        detailed.append(
            {
                "id": voice_id,
                "engine": engine,
                "ready": bool(info.get("ready")),
                "status": info.get("status") or "",
            }
        )
    return detailed


def get_tts_core(lang_code: Optional[str] = None) -> TTSCore:
    return TTSCore(lang_code=lang_code)


if __name__ == "__main__":
    import sys
    print("Habibi-only TTS. Use the API with voice sample + ref_text.", file=sys.stderr)
    sys.exit(2)
