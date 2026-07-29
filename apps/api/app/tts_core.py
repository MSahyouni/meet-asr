# tts_core.py — TTS engines: MMS + Habibi + OmniVoice
import logging
import pathlib
from functools import lru_cache
from typing import Optional

from app.config import settings

logger = logging.getLogger("tts_core")


# ---------------------------------------------------------------------------
# P2 — تشكيل عربي قبل TTS (mishkal when TTS_DIACRITIZE=1)
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
    Enable with TTS_DIACRITIZE=1 and install mishkal (pip install mishkal).
    """
    if not getattr(settings, "TTS_DIACRITIZE", False):
        return text
    try:
        from app.tts.diacritize import add_diacritics
        return add_diacritics(text)
    except ImportError:
        return text

# Limits and defaults
TTS_TEXT_MAX_LEN = 5000
TTS_SPEED_MIN = 0.25
TTS_SPEED_MAX = 2.0
TTS_DEFAULT_VOICE = "ar_mms"
TTS_ALLOWED_ENGINES = {"auto", "mms", "habibi", "omnivoice"}
TTS_REMOVED_ENGINES = {"xtts", "xtts_v2"}

# Static list of supported voices/models after cleanup.
TTS_KNOWN_VOICES = [
    "habibi_unified", "habibi_specialized",
    "omnivoice",
    "ar_mms",
]

# voice id -> engine family (for status / routing hints)
TTS_VOICE_ENGINE = {
    "omnivoice": "omnivoice",
    "habibi_unified": "habibi",
    "habibi_specialized": "habibi",
    "ar_mms": "mms",
}


def _use_mms_for_arabic(text: str) -> bool:
    """True if we should route to MMS-TTS (Arabic text + MMS enabled)."""
    if not getattr(settings, "TTS_MMS_ENABLED", True):
        return False
    try:
        from app.tts.lang_detect import is_arabic
        return is_arabic(text)
    except ImportError:
        return False


def _resolve_user_speaker_ref_if_available(user_email: Optional[str], speaker_ref: Optional[str]) -> Optional[str]:
    """Return a valid speaker_ref filename if available for the user; otherwise None."""
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


def _habibi_model_choice(requested_voice: str) -> str:
    voice = (requested_voice or "").strip().lower()
    if voice in ("habibi_unified", "habibi_specialized"):
        return voice
    return "habibi_unified"


class TTSCore:
    """
    TTS engines: OmniVoice (voice clone, optional ref_text) + Habibi (dialectal Arabic + voice clone) + MMS-TTS Arabic.
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
        Engines: mms (Arabic), habibi (dialectal Arabic + voice clone).

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
        if engine_requested in TTS_REMOVED_ENGINES:
            raise ValueError(
                "محرك xtts_v2 أُزيل من المشروع. "
                "استخدم engine=habibi مع بصمة + ref_text، أو engine=mms للعربي بدون استنساخ."
            )
        if engine_requested not in TTS_ALLOWED_ENGINES:
            raise ValueError(f"engine must be one of: {', '.join(sorted(TTS_ALLOWED_ENGINES))}")

        # Route Arabic through OmniVoice / Habibi / MMS.
        # Note: voice=ar_mms must NOT skip cloning in engine=auto — only engine=mms forces MMS.
        requested_voice = (voice or "").strip() or TTS_DEFAULT_VOICE
        requested_voice_lc = requested_voice.lower()
        prefer_mms_voice = requested_voice_lc in ("ar_mms",)
        arabic_detected = _use_mms_for_arabic(text) or prefer_mms_voice
        auto_fallback_used = False

        # 1) OmniVoice (explicit or auto with uploaded voice sample)
        if engine_requested in ("auto", "omnivoice"):
            run_omnivoice = engine_requested == "omnivoice"
            omnivoice_speaker_ref = None
            if engine_requested == "auto":
                # Prefer clone when a sample exists, even if UI defaulted voice to ar_mms.
                omnivoice_speaker_ref = _resolve_user_speaker_ref_if_available(
                    user_email=user_email, speaker_ref=speaker_ref
                )
                run_omnivoice = bool(omnivoice_speaker_ref)

            if run_omnivoice:
                text_o = _preprocess_text(text)
                text_o = maybe_diacritize(text_o)
                if not (user_email or "").strip():
                    if engine_requested == "omnivoice":
                        raise ValueError("OmniVoice requires user_email and uploaded voice sample")
                else:
                    try:
                        from app.tts.voice_profiles import get_user_speaker_ref_text, resolve_user_speaker_path
                        from app.tts.tts_omnivoice import synthesize_omnivoice

                        ref_audio = resolve_user_speaker_path(
                            user_email=user_email,
                            speaker_ref=omnivoice_speaker_ref or speaker_ref,
                        )
                        # OmniVoice supports omitting ref_text (it will auto-transcribe ref_audio).
                        resolved_ref_text = (ref_text or "").strip() or (
                            get_user_speaker_ref_text(user_email, ref_audio.name) or ""
                        )
                        resolved_ref_text = resolved_ref_text.strip() or None

                        result = synthesize_omnivoice(
                            text=text_o,
                            ref_audio_path=str(ref_audio),
                            ref_text=resolved_ref_text,
                            speed=speed,
                            out_path=out_path,
                        )
                        result.update({
                            "engine_used": "omnivoice",
                            "arabic_detected": arabic_detected,
                            "fallback_used": False,
                            "requested_voice": requested_voice,
                            "resolved_voice": "omnivoice",
                            "speaker_ref": ref_audio.name,
                        })
                        return result
                    except (ImportError, RuntimeError, FileNotFoundError, ValueError) as e:
                        if engine_requested == "omnivoice":
                            raise ValueError(f"OmniVoice failed: {e}") from e
                        auto_fallback_used = True
                        logger.warning("Auto OmniVoice failed, falling back to built-in engines: %s", e)
                    except Exception as e:
                        if engine_requested == "omnivoice":
                            logger.exception("OmniVoice runtime error: %s", e)
                            raise RuntimeError(f"OmniVoice failed: {e}") from e
                        auto_fallback_used = True
                        logger.warning("Auto OmniVoice failed, falling back: %s", e)

        # 2) Habibi (explicit or auto with sample + ref_text)
        if engine_requested in ("auto", "habibi"):
            run_habibi = engine_requested == "habibi"
            habibi_speaker_ref = None
            if engine_requested == "auto":
                habibi_speaker_ref = _resolve_user_speaker_ref_if_available(
                    user_email=user_email, speaker_ref=speaker_ref
                )
                run_habibi = bool(habibi_speaker_ref)
            if run_habibi:
                text_h = _preprocess_text(text)
                text_h = maybe_diacritize(text_h)
                if not (user_email or "").strip():
                    if engine_requested == "habibi":
                        raise ValueError("Habibi requires user_email and uploaded voice sample")
                    run_habibi = False
                else:
                    try:
                        from app.tts.voice_profiles import get_user_speaker_ref_text, resolve_user_speaker_path
                        from app.tts.tts_habibi import synthesize_habibi

                        ref_audio = resolve_user_speaker_path(
                            user_email=user_email,
                            speaker_ref=habibi_speaker_ref or speaker_ref,
                        )
                        resolved_ref_text = (
                            (ref_text or "").strip()
                            or get_user_speaker_ref_text(user_email, ref_audio.name)
                        )
                        if not (resolved_ref_text or "").strip():
                            if engine_requested == "habibi":
                                raise ValueError(
                                    "Habibi requires ref_text matching the voice sample only "
                                    "(not the full text to generate). Add it in the form or when uploading the sample."
                                )
                            run_habibi = False
                        else:
                            requested_model = _habibi_model_choice(requested_voice)
                            result = synthesize_habibi(
                                text=text_h,
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
                        if engine_requested == "habibi":
                            raise ValueError(f"Habibi failed: {e}") from e
                        auto_fallback_used = True
                        logger.warning("Auto Habibi failed, falling back to built-in engines: %s", e)
                    except Exception as e:
                        if engine_requested == "habibi":
                            logger.exception("Habibi runtime error: %s", e)
                            raise RuntimeError(_format_habibi_runtime_error(e)) from e
                        auto_fallback_used = True
                        logger.warning("Auto Habibi failed, falling back: %s", e)

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
            "Use engine=habibi with speaker profile + ref_text, or engine=mms for Arabic text."
        )


def list_voices() -> list:
    """
    Return list of available TTS voice IDs.
    Uses static TTS_KNOWN_VOICES for enabled engines only.
    """
    return list(TTS_KNOWN_VOICES)


def _engine_status_omnivoice() -> dict:
    try:
        from app.tts.tts_omnivoice import omnivoice_readiness

        ready, status, infer_bin = omnivoice_readiness()
        return {
            "engine": "omnivoice",
            "ready": bool(ready),
            "status": status,
            "infer_bin": infer_bin,
        }
    except Exception as e:
        return {"engine": "omnivoice", "ready": False, "status": str(e)}


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


def _engine_status_mms() -> dict:
    if not getattr(settings, "TTS_MMS_ENABLED", True):
        return {"engine": "mms", "ready": False, "status": "معطّل عبر TTS_MMS_ENABLED=0"}
    try:
        import importlib.util

        if importlib.util.find_spec("transformers") is None:
            return {"engine": "mms", "ready": False, "status": "transformers غير مثبت"}
        return {"engine": "mms", "ready": True, "status": "جاهز"}
    except Exception as e:
        return {"engine": "mms", "ready": False, "status": str(e)}


def list_engine_status() -> list[dict]:
    """Return readiness for each TTS engine family."""
    return [
        _engine_status_omnivoice(),
        _engine_status_habibi(),
        _engine_status_mms(),
    ]


def list_voices_detailed() -> list[dict]:
    """Voice IDs with per-engine readiness (for GET /tts/voices)."""
    by_engine = {item["engine"]: item for item in list_engine_status()}
    detailed = []
    for voice_id in TTS_KNOWN_VOICES:
        engine = TTS_VOICE_ENGINE.get(voice_id, "unknown")
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
