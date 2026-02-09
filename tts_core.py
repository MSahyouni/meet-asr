# tts_core.py — TTS باستخدام Kokoro-82M (lazy singleton، لا إعادة تحميل بين الطلبات)
import logging
import os
import pathlib
from typing import Optional

from config import settings

logger = logging.getLogger("tts_core")


# ---------------------------------------------------------------------------
# P2 — تشكيل عربي قبل TTS (stub: لا dependency إضافي حتى تفعيل CAMeL / Farasa)
# TODO: when TTS_DIACRITIZE=1, plug in CAMeL Tools or Farasa for Arabic diacritization
#       to improve pronunciation. Set TTS_DIACRITIZE=1 in env when backend is ready.
# ---------------------------------------------------------------------------
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

# Static list of known Kokoro-82M voices (from hexgrad/Kokoro-82M VOICES.md).
# Used when the library does not expose list_voices(). Document: https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md
TTS_KNOWN_VOICES = [
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


def _get_pipeline():
    """Load Kokoro pipeline once; reuse on subsequent calls."""
    global _PIPELINE
    if _PIPELINE is not None:
        return _PIPELINE
    # Ensure HF cache is project-local (config already sets HF_HOME; kokoro uses hf_hub_download)
    os.environ.setdefault("HF_HOME", str(settings.HF_DIR))
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(settings.HF_DIR / "hub"))
    try:
        from kokoro import KPipeline
        logger.info("Loading Kokoro TTS model (first run may download ~327MB to %s)...", settings.HF_DIR)
        _PIPELINE = KPipeline(
            lang_code=os.getenv("TTS_LANG_CODE", TTS_DEFAULT_LANG),
            repo_id=KOKORO_REPO_ID,
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


class TTSCore:
    """
    TTS باستخدام Kokoro-82M. النموذج يُحمّل مرة واحدة (singleton) ولا يُعاد تحميله بين الطلبات.
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
    ) -> dict:
        """
        Convert text to speech and save as WAV.

        Returns:
            dict with keys: audio_path, sample_rate, duration_sec, voice
        """
        # Normalize and validate text
        text = (text or "").strip()
        if not text:
            raise ValueError("Text cannot be empty.")
        text = maybe_diacritize(text)
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

        # Default voice
        voice = (voice or "").strip() or TTS_DEFAULT_VOICE
        if voice.lower() == "default":
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
