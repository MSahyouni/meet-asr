from __future__ import annotations

import re

import numpy as np


def apply_speed_numpy(waveform: np.ndarray, speed: float) -> np.ndarray:
    """Stretch/compress waveform. speed < 1 => slower/longer, speed > 1 => faster/shorter."""
    speed_f = float(speed or 1.0)
    speed_f = max(0.25, min(2.0, speed_f))
    if abs(speed_f - 1.0) < 1e-6 or waveform.size == 0:
        return waveform
    src_idx = np.arange(waveform.shape[0], dtype=np.float32)
    target_len = max(1, int(round(waveform.shape[0] / speed_f)))
    dst_idx = np.linspace(0.0, waveform.shape[0] - 1, num=target_len, dtype=np.float32)
    return np.interp(dst_idx, src_idx, waveform).astype(np.float32)


def trim_ref_text_for_duration(ref_text: str, audio_seconds: float, bytes_per_second: float = 13.0) -> str:
    """Keep only the portion of ref_text that can plausibly match the reference audio."""
    text = re.sub(r"\s+", " ", (ref_text or "").strip())
    if not text or audio_seconds <= 0:
        return text
    max_bytes = max(48, int(audio_seconds * bytes_per_second))
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    parts = re.split(r"(\s+)", text)
    out = ""
    for part in parts:
        trial = out + part
        if len(trial.encode("utf-8")) > max_bytes:
            break
        out = trial
    out = out.strip()
    if out:
        return out
    return encoded[:max_bytes].decode("utf-8", errors="ignore").strip()
