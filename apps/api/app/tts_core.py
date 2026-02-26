# tts_core.py — TTS باستخدام Kokoro-82M (lazy singleton، لا إعادة تحميل بين الطلبات)
import logging
import os
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
TTS_SAMPLE_RATE = 24000
TTS_DEFAULT_VOICE = "af_heart"
TTS_DEFAULT_LANG = "a"  # American English; Kokoro supports a,b,e,f,h,i,j,p,z
TTS_ALLOWED_ENGINES = {"auto", "kokoro", "mms", "xtts"}

# Static list of known Kokoro-82M voices (from hexgrad/Kokoro-82M VOICES.md).
# ar_mms: Arabic MMS-TTS (single voice, optional seed). ar_1..ar_4: tts_arabic (4 voices, optional pkg).
TTS_KNOWN_VOICES = [
    "xtts",
    "ar_mms", "ar_1", "ar_2", "ar_3", "ar_4",  # Arabic
    "af_heart", "af_alloy", "af_aoede", "af_bella", "af_jessica", "af_kore", "af_nicole", "af_nova", "af_river", "af_sarah", "af_sky",
    "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam", "am_michael", "am_onyx", "am_puck", "am_santa",
    "bf_alice", "bf_emma", "bf_isabella", "bf_lily", "bm_daniel", "bm_fable", "bm_george", "bm_lewis",
    "jf_alpha", "jf_gongitsune", "jf_nezumi", "jf_tebukuro", "jm_kumo",
    "zf_xiaobei", "zf_xiaoni", "zf_xiaoxiao", "zf_xiaoyi", "zm_yunjian", "zm_yunxi", "zm_yunxia", "zm_yunyang",
    "ef_dora", "em_alex", "em_santa", "ff_siwis", "hf_alpha", "hf_beta", "hm_omega", "hm_psi",
    "if_sara", "im_nicola", "pf_dora", "pm_alex", "pm_santa",
]

# Singleton pipeline (lazy-loaded once per process)
_PIPELINE = None


# Hugging Face cache: use project HF_DIR so model downloads to data/.hf (resumable)
KOKORO_REPO_ID = "hexgrad/Kokoro-82M"


def _kokoro_model_ready(model_dir: pathlib.Path) -> bool:
    config_file = model_dir / "config.json"
    has_weights = any(model_dir.glob("*.pth"))
    return config_file.exists() and has_weights


def _get_pipeline():
    """Load Kokoro pipeline once; reuse on subsequent calls."""
    global _PIPELINE
    if _PIPELINE is not None:
        return _PIPELINE
    # Ensure HF cache is project-local (config already sets HF_HOME; kokoro uses hf_hub_download)
    os.environ.setdefault("HF_HOME", str(settings.HF_DIR))
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(settings.HF_DIR / "hub"))
    kokoro_dir = pathlib.Path(settings.TTS_KOKORO_DIR).resolve()
    kokoro_dir.mkdir(parents=True, exist_ok=True)
    try:
        if not _kokoro_model_ready(kokoro_dir):
            if not getattr(settings, "TTS_KOKORO_ALLOW_DOWNLOAD", True):
                raise RuntimeError(
                    f"Kokoro model not found in {kokoro_dir}. "
                    "Place model files there or set TTS_KOKORO_ALLOW_DOWNLOAD=1 for first-time fetch."
                )
            from huggingface_hub import snapshot_download

            logger.info("Downloading Kokoro model into fixed folder: %s", kokoro_dir)
            snapshot_download(
                repo_id=KOKORO_REPO_ID,
                local_dir=str(kokoro_dir),
                local_dir_use_symlinks=False,
            )

        from kokoro import KPipeline
        logger.info("Loading Kokoro TTS model from %s", kokoro_dir)
        _PIPELINE = KPipeline(
            lang_code=os.getenv("TTS_LANG_CODE", TTS_DEFAULT_LANG),
            repo_id=str(kokoro_dir),
        )
        logger.info("Kokoro TTS pipeline loaded (singleton).")
        return _PIPELINE
    except ImportError as e:
        raise RuntimeError(
            "TTS requires the 'kokoro' package. Install with: pip install kokoro"
        ) from e
    except Exception as e:
        logger.exception("Failed to load Kokoro pipeline: %s", e)
        raise RuntimeError(f"Failed to load TTS model: {e}") from e


def _use_mms_for_arabic(text: str) -> bool:
    """True if we should route to MMS-TTS (Arabic text + MMS enabled)."""
    if not getattr(settings, "TTS_MMS_ENABLED", True):
        return False
    try:
        from app.tts.lang_detect import is_arabic
        return is_arabic(text)
    except ImportError:
        return False


class TTSCore:
    """
    TTS: Kokoro-82M (English/other) + MMS-TTS (Arabic).
    Arabic text is auto-detected and routed to facebook/mms-tts-ara (offline).
    """

    def __init__(self, lang_code: Optional[str] = None):
        self.lang_code = (lang_code or os.getenv("TTS_LANG_CODE", TTS_DEFAULT_LANG)).strip() or TTS_DEFAULT_LANG

    def _pipeline(self):
        return _get_pipeline()

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
    ) -> dict:
        """
        Convert text to speech and save as WAV.
        Arabic: ar_mms (MMS-TTS + optional seed), ar_1..ar_4 (tts_arabic 4 voices). Other -> Kokoro.

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
        if engine_requested not in TTS_ALLOWED_ENGINES:
            raise ValueError(f"engine must be one of: {', '.join(sorted(TTS_ALLOWED_ENGINES))}")

        # Route Arabic: ar_1..ar_4 -> tts_arabic (4 voices), else ar_mms -> MMS-TTS (with optional seed)
        requested_voice = (voice or "").strip() or TTS_DEFAULT_VOICE
        arabic_detected = _use_mms_for_arabic(text)

        if engine_requested == "xtts":
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
                    "engine_used": "xtts",
                    "arabic_detected": arabic_detected,
                    "fallback_used": False,
                    "requested_voice": requested_voice,
                    "resolved_voice": result.get("voice", "xtts"),
                    "speaker_ref": result.get("speaker_ref"),
                })
                return result
            except (ImportError, RuntimeError, FileNotFoundError, ValueError) as e:
                raise ValueError(f"XTTS failed: {e}") from e

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

        if engine_requested == "kokoro":
            arabic_detected = False

        if arabic_detected:
            text = _preprocess_text(text)
            text = maybe_diacritize(text)
            voice_ar = requested_voice.strip().lower()
            fallback_used = False
            if voice_ar in ("ar_1", "ar_2", "ar_3", "ar_4"):
                try:
                    from app.tts.tts_arabic_multi import synthesize_arabic_multi
                    result = synthesize_arabic_multi(text=text, voice=voice_ar, speed=speed, out_path=out_path)
                    result.update({
                        "engine_used": "arabic_multi",
                        "arabic_detected": True,
                        "fallback_used": False,
                        "requested_voice": requested_voice,
                        "resolved_voice": result.get("voice", voice_ar),
                    })
                    return result
                except (ImportError, RuntimeError) as e:
                    logger.warning("tts_arabic multi-voice failed: %s", e)
                    fallback_used = True
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

        # Kokoro path (English / non-Arabic)
        text = _preprocess_text(text)
        text = maybe_diacritize(text)
        voice = requested_voice
        if voice.lower() == "default":
            voice = TTS_DEFAULT_VOICE
        # If user passed Arabic voice for non-Arabic text, use default Kokoro voice
        if voice in ("ar_mms", "ar_1", "ar_2", "ar_3", "ar_4"):
            voice = TTS_DEFAULT_VOICE

        # Output path: ensure under outputs/tts/
        out_dir = pathlib.Path(settings.OUTPUTS_DIR) / "tts"
        out_dir.mkdir(parents=True, exist_ok=True)
        if not out_path or not pathlib.Path(out_path).suffix:
            import time
            base = f"tts_{int(time.time() * 1000)}"
            out_path = str(out_dir / f"{base}.wav")
        else:
            p = pathlib.Path(out_path)
            if not p.is_absolute():
                p = out_dir / p.name
            p.parent.mkdir(parents=True, exist_ok=True)
            out_path = str(p.resolve())

        pipeline = self._pipeline()
        try:
            generator = pipeline(text, voice=voice, speed=speed)
        except Exception as e:
            raise RuntimeError(f"TTS synthesis failed (voice={voice!r}): {e}") from e

        chunks = []
        for _gs, _ps, audio in generator:
            chunks.append(audio)

        if not chunks:
            raise RuntimeError("TTS produced no audio segments.")

        import numpy as np
        import soundfile as sf

        audio_concat = np.concatenate(chunks, axis=0) if len(chunks) > 1 else chunks[0]
        if hasattr(audio_concat, "numpy"):
            audio_concat = audio_concat.numpy()
        audio_concat = np.asarray(audio_concat, dtype=np.float32)
        if audio_concat.ndim > 1:
            audio_concat = audio_concat.flatten()

        sf.write(out_path, audio_concat, TTS_SAMPLE_RATE)
        duration_sec = len(audio_concat) / float(TTS_SAMPLE_RATE)

        return {
            "audio_path": out_path,
            "sample_rate": TTS_SAMPLE_RATE,
            "duration_sec": round(duration_sec, 3),
            "voice": voice,
            "engine_used": "kokoro",
            "arabic_detected": False,
            "fallback_used": False,
            "requested_voice": requested_voice,
            "resolved_voice": voice,
        }


def list_voices() -> list:
    """
    Return list of available TTS voice IDs.
    Uses static TTS_KNOWN_VOICES (Kokoro-82M VOICES.md). Does not load the model.
    If the Kokoro library later exposes a lightweight way to list voices, it can be used here.
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
