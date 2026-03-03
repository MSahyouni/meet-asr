# tts_core.py — TTS engines: MMS + XTTS v2 + Habibi
import logging
import pathlib
from functools import lru_cache
from typing import Optional

from app.config import settings

logger = logging.getLogger("tts_core")


# ---------------------------------------------------------------------------
# P2 — تشكيل عربي قبل TTS (stub: لا dependency إضافي حتى تفعيل CAMeL / Farasa)
# TODO: when TTS_DIACRITIZE=1, plug in CAMeL Tools or Farasa for Arabic diacritization
#       to improve pronunciation. Set TTS_DIACRITIZE=1 in env when backend is ready.
# ---------------------------------------------------------------------------
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


def maybe_diacritize(text: str) -> str:
    """
    Optional preprocessing: add Arabic diacritics (تشكيل) before TTS for better pronunciation.
    Default: returns text unchanged. When TTS_DIACRITIZE=1 and a backend is plugged in,
    returns diacritized text (e.g. via CAMeL Tools or Farasa).
    """
    if not getattr(settings, "TTS_DIACRITIZE", False):
        return text
    # Stub: no heavy deps yet; plug in here when adding CAMeL/Farasa
    return text

# Limits and defaults
TTS_TEXT_MAX_LEN = 5000
TTS_SPEED_MIN = 0.5
TTS_SPEED_MAX = 2.0
TTS_DEFAULT_VOICE = "ar_mms"
TTS_ALLOWED_ENGINES = {"auto", "mms", "xtts_v2", "xtts", "habibi"}

# Static list of supported voices/models after cleanup.
TTS_KNOWN_VOICES = [
    "xtts_v2",
    "habibi_unified", "habibi_specialized",
    "ar_mms",
]


def _use_mms_for_arabic(text: str) -> bool:
    """True if we should route to MMS-TTS (Arabic text + MMS enabled)."""
    if not getattr(settings, "TTS_MMS_ENABLED", True):
        return False
    try:
        from app.tts.lang_detect import is_arabic
        return is_arabic(text)
    except ImportError:
        return False


def _resolve_xtts_speaker_ref_if_available(user_email: Optional[str], speaker_ref: Optional[str]) -> Optional[str]:
    """Return a valid XTTS speaker_ref filename if available for the user; otherwise None."""
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
            "Habibi model download failed بسبب مشكلة شبكة/ DNS عند الوصول إلى Hugging Face. "
            "تحقق من الاتصال ثم أعد المحاولة (التنزيل يُستكمل تلقائيًا من الجزء السابق). "
            "مؤقتًا استخدم engine=auto أو engine=mms. "
            f"Original error: {raw}"
        )
    return f"Habibi failed: {raw}"


class TTSCore:
    """
    TTS engines after cleanup: XTTS v2 + Habibi + MMS-TTS Arabic.
    """

    def __init__(self, lang_code: Optional[str] = None):
        self.lang_code = (lang_code or "ar").strip() or "ar"

    def synthesize(
        self,
        text: str,
        voice: str = "",
        speed: float = 1.0,
        out_path: str = "",
        seed: Optional[int] = None,
        engine: str = "auto",
        user_email: Optional[str] = None,
        speaker_ref: Optional[str] = None,
        ref_text: Optional[str] = None,
        dialect: Optional[str] = None,
    ) -> dict:
        """
        Convert text to speech and save as WAV.
        Engines: mms (Arabic), xtts_v2 (voice clone), habibi (dialectal Arabic).

        Returns:
            dict with keys: audio_path, sample_rate, duration_sec, voice
        """
        # Normalize and validate text
        text = (text or "").strip()
        if not text:
            raise ValueError("Text cannot be empty.")
        if len(text) > TTS_TEXT_MAX_LEN:
            raise ValueError(
                f"Text length ({len(text)}) exceeds maximum ({TTS_TEXT_MAX_LEN} characters)."
            )

        # Validate speed
        try:
            speed_f = float(speed)
        except (TypeError, ValueError):
            raise ValueError(f"Speed must be a number between {TTS_SPEED_MIN} and {TTS_SPEED_MAX}.")
        if not (TTS_SPEED_MIN <= speed_f <= TTS_SPEED_MAX):
            raise ValueError(
                f"Speed must be between {TTS_SPEED_MIN} and {TTS_SPEED_MAX}, got {speed_f}."
            )
        speed = speed_f
        engine_requested = (engine or "auto").strip().lower()
        if engine_requested == "xtts":
            engine_requested = "xtts_v2"
        if engine_requested not in TTS_ALLOWED_ENGINES:
            raise ValueError(f"engine must be one of: {', '.join(sorted(TTS_ALLOWED_ENGINES))}")

        # Route Arabic through MMS/Habibi, with XTTS priority in auto if speaker exists.
        requested_voice = (voice or "").strip() or TTS_DEFAULT_VOICE
        requested_voice_lc = requested_voice.lower()
        force_arabic_voice = requested_voice_lc in ("ar_mms",)
        arabic_detected = _use_mms_for_arabic(text) or force_arabic_voice
        auto_fallback_used = False

        if engine_requested == "auto":
            xtts_speaker_ref = None
            if not force_arabic_voice:
                xtts_speaker_ref = _resolve_xtts_speaker_ref_if_available(user_email=user_email, speaker_ref=speaker_ref)
            if xtts_speaker_ref:
                xtts_text = maybe_diacritize(_preprocess_text(text))
                try:
                    from app.tts.tts_xtts import synthesize_xtts

                    result = synthesize_xtts(
                        text=xtts_text,
                        voice=requested_voice,
                        speed=speed,
                        out_path=out_path,
                        user_email=user_email,
                        speaker_ref=xtts_speaker_ref,
                    )
                    result.update({
                        "engine_used": "xtts_v2",
                        "arabic_detected": arabic_detected,
                        "fallback_used": False,
                        "requested_voice": requested_voice,
                        "resolved_voice": result.get("voice", "xtts_v2"),
                        "speaker_ref": result.get("speaker_ref") or xtts_speaker_ref,
                    })
                    return result
                except (ImportError, RuntimeError, FileNotFoundError, ValueError) as e:
                    auto_fallback_used = True
                    logger.warning("Auto XTTS failed, falling back to built-in engines: %s", e)

        if engine_requested == "xtts_v2":
            text = _preprocess_text(text)
            text = maybe_diacritize(text)
            try:
                from app.tts.tts_xtts import synthesize_xtts
                result = synthesize_xtts(
                    text=text,
                    voice=requested_voice,
                    speed=speed,
                    out_path=out_path,
                    user_email=user_email,
                    speaker_ref=speaker_ref,
                )
                result.update({
                    "engine_used": "xtts_v2",
                    "arabic_detected": arabic_detected,
                    "fallback_used": False,
                    "requested_voice": requested_voice,
                    "resolved_voice": result.get("voice", "xtts_v2"),
                    "speaker_ref": result.get("speaker_ref"),
                })
                return result
            except (ImportError, RuntimeError, FileNotFoundError, ValueError) as e:
                raise ValueError(f"XTTS failed: {e}") from e

        if engine_requested == "habibi":
            text = _preprocess_text(text)
            text = maybe_diacritize(text)
            if not (user_email or "").strip():
                raise ValueError("Habibi requires user_email and uploaded voice sample")
            try:
                from app.tts.voice_profiles import get_user_speaker_ref_text, resolve_user_speaker_path
                from app.tts.tts_habibi import synthesize_habibi

                ref_audio = resolve_user_speaker_path(user_email=user_email, speaker_ref=speaker_ref)
                resolved_ref_text = (
                    (ref_text or "").strip()
                    or get_user_speaker_ref_text(user_email, ref_audio.name)
                    or text
                )
                if not (resolved_ref_text or "").strip():
                    raise ValueError(
                        "Habibi requires ref_text. Upload voice sample with ref_text or provide ref_text in /tts request."
                    )
                requested_model = requested_voice if requested_voice else "habibi_unified"
                result = synthesize_habibi(
                    text=text,
                    ref_audio_path=str(ref_audio),
                    ref_text=resolved_ref_text,
                    speed=speed,
                    out_path=out_path,
                    model_choice=requested_model,
                    dialect=dialect or "UNK",
                )
                result.update({
                    "engine_used": "habibi",
                    "arabic_detected": True,
                    "fallback_used": False,
                    "requested_voice": requested_voice,
                    "resolved_voice": result.get("voice", requested_model),
                    "speaker_ref": ref_audio.name,
                    "dialect": result.get("dialect", (dialect or "UNK").upper()),
                })
                return result
            except (ImportError, RuntimeError, FileNotFoundError, ValueError) as e:
                raise ValueError(f"Habibi failed: {e}") from e
            except Exception as e:
                logger.exception("Habibi runtime error: %s", e)
                raise RuntimeError(_format_habibi_runtime_error(e)) from e

        if engine_requested == "mms":
            text = _preprocess_text(text)
            text = maybe_diacritize(text)
            try:
                from app.tts.tts_mms import synthesize_mms
                result = synthesize_mms(text=text, voice="ar_mms", speed=speed, out_path=out_path, seed=seed)
                result.update({
                    "engine_used": "mms_arabic",
                    "arabic_detected": arabic_detected,
                    "fallback_used": False,
                    "requested_voice": requested_voice,
                    "resolved_voice": "ar_mms",
                })
                return result
            except (ImportError, RuntimeError) as e:
                raise ValueError(f"MMS failed: {e}") from e

        if arabic_detected:
            text = _preprocess_text(text)
            text = maybe_diacritize(text)
            fallback_used = auto_fallback_used
            try:
                from app.tts.tts_mms import synthesize_mms
                result = synthesize_mms(text=text, voice="ar_mms", speed=speed, out_path=out_path, seed=seed)
                result.update({
                    "engine_used": "mms_arabic",
                    "arabic_detected": True,
                    "fallback_used": fallback_used,
                    "requested_voice": requested_voice,
                    "resolved_voice": "ar_mms",
                })
                return result
            except (ImportError, RuntimeError) as e:
                logger.warning("MMS-TTS failed: %s", e)
                raise ValueError(
                    f"Arabic TTS failed: {e}. Ensure transformers>=4.33 and torch are installed."
                ) from e

        raise ValueError(
            "No available non-Arabic fallback engine. "
            "Use engine=xtts_v2 with speaker profile, engine=habibi for Arabic dialects, or engine=mms for Arabic text."
        )


def list_voices() -> list:
    """
    Return list of available TTS voice IDs.
    Uses static TTS_KNOWN_VOICES for enabled engines only.
    """
    return list(TTS_KNOWN_VOICES)


def get_tts_core(lang_code: Optional[str] = None) -> TTSCore:
    """Return a TTSCore instance (shared pipeline via module singleton)."""
    return TTSCore(lang_code=lang_code)


if __name__ == "__main__":
    # Small snippet: generate one WAV to outputs/tts/ (no model reload on second call)
    import sys
    core = get_tts_core()
    text = sys.argv[1] if len(sys.argv) > 1 else "Hello, this is a test."
    out_dir = pathlib.Path(settings.OUTPUTS_DIR) / "tts"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = str(out_dir / "tts_sample.wav")
    try:
        result = core.synthesize(text, voice=TTS_DEFAULT_VOICE, speed=1.0, out_path=out_path)
        print("OK:", result)
        # Second call reuses the same pipeline (no reload)
        result2 = core.synthesize("Second sentence.", voice=TTS_DEFAULT_VOICE, speed=1.0, out_path="")
        print("OK (no reload):", result2)
    except Exception as e:
        print("Error:", e, file=sys.stderr)
        sys.exit(1)
