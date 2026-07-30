"""Inspect Habibi/OmniVoice reference audio samples before synthesis."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger("tts.voice_check")

REF_IDEAL_MIN_SEC = 3.0
REF_IDEAL_MAX_SEC = 10.0
REF_HARD_MAX_SEC = 15.0
REF_TOO_SHORT_SEC = 1.2
SILENCE_RMS = 0.012
SILENCE_RATIO_WARN = 0.45


def _load_mono(path: str) -> tuple[np.ndarray, int]:
    import soundfile as sf

    try:
        data, sr = sf.read(path, dtype="float32", always_2d=False)
    except Exception:
        # Fallback for formats soundfile may not decode.
        import torchaudio

        audio, sr = torchaudio.load(path)
        if audio.shape[0] > 1:
            audio = audio.mean(dim=0, keepdim=True)
        data = audio.squeeze(0).cpu().numpy().astype(np.float32)
        return data, int(sr)

    if getattr(data, "ndim", 1) > 1:
        data = np.mean(data, axis=1)
    return np.asarray(data, dtype=np.float32), int(sr)


def inspect_voice_sample(
    path: str,
    *,
    has_ref_text: bool = False,
    ref_text: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return duration / silence stats and actionable warnings for Habibi cloning.
    """
    warnings: List[dict] = []
    duration_sec = 0.0
    silence_ratio = 0.0
    rms = 0.0

    try:
        wave, sr = _load_mono(path)
        if sr <= 0 or wave.size == 0:
            warnings.append(
                {"level": "error", "code": "empty_audio", "message": "ملف البصمة فارغ أو غير قابل للقراءة"}
            )
        else:
            duration_sec = float(len(wave) / float(sr))
            rms = float(np.sqrt(np.mean(np.square(wave)) + 1e-12))
            # Frame-based silence (~20 ms)
            frame = max(1, int(sr * 0.02))
            n = (len(wave) // frame) * frame
            if n >= frame:
                frames = wave[:n].reshape(-1, frame)
                frame_rms = np.sqrt(np.mean(np.square(frames), axis=1) + 1e-12)
                silence_ratio = float(np.mean(frame_rms < SILENCE_RMS))
    except Exception as exc:
        logger.warning("inspect_voice_sample failed for %s: %s", path, exc)
        warnings.append(
            {
                "level": "error",
                "code": "read_failed",
                "message": f"تعذّر قراءة البصمة: {exc}",
            }
        )

    if duration_sec > 0:
        if duration_sec < REF_TOO_SHORT_SEC:
            warnings.append(
                {
                    "level": "error",
                    "code": "too_short",
                    "message": f"البصمة قصيرة جداً ({duration_sec:.1f}s) — يُفضّل 3–10 ثوانٍ",
                }
            )
        elif duration_sec < REF_IDEAL_MIN_SEC:
            warnings.append(
                {
                    "level": "warn",
                    "code": "short",
                    "message": f"البصمة أقصر من المثالي ({duration_sec:.1f}s) — الأفضل ≥ {REF_IDEAL_MIN_SEC:.0f}s",
                }
            )
        if duration_sec > REF_HARD_MAX_SEC:
            warnings.append(
                {
                    "level": "warn",
                    "code": "too_long",
                    "message": f"البصمة طويلة ({duration_sec:.1f}s) — Habibi يقصّها؛ قصّها يدوياً إلى 5–10 ثوانٍ",
                }
            )
        elif duration_sec > REF_IDEAL_MAX_SEC:
            warnings.append(
                {
                    "level": "warn",
                    "code": "long",
                    "message": f"البصمة أطول من المثالي ({duration_sec:.1f}s) — الأفضل ≤ {REF_IDEAL_MAX_SEC:.0f}s",
                }
            )
        if silence_ratio >= SILENCE_RATIO_WARN:
            warnings.append(
                {
                    "level": "warn",
                    "code": "much_silence",
                    "message": f"صمت كثير في العينة ({silence_ratio * 100:.0f}%) — قصّ البداية/النهاية",
                }
            )
        if rms > 0 and rms < 0.01:
            warnings.append(
                {
                    "level": "warn",
                    "code": "quiet",
                    "message": "العينة هادئة جداً — قد يضعف الاستنساخ",
                }
            )

    ref_value = (ref_text or "").strip()
    if not has_ref_text and not ref_value:
        warnings.append(
            {
                "level": "error",
                "code": "missing_ref_text",
                "message": "لا يوجد ref_text — اكتب ما يُسمع في البصمة أو استخرجه عبر ASR",
            }
        )

    blocking = any(w.get("level") == "error" for w in warnings)
    return {
        "ok": True,
        "duration_sec": round(duration_sec, 3),
        "silence_ratio": round(silence_ratio, 3),
        "rms": round(rms, 5),
        "has_ref_text": bool(has_ref_text or ref_value),
        "ideal_min_sec": REF_IDEAL_MIN_SEC,
        "ideal_max_sec": REF_IDEAL_MAX_SEC,
        "warnings": warnings,
        "blocking": blocking,
    }
