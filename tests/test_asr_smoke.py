# tests/test_asr_smoke.py — light ASR smoke test (CPU; skips if no local Whisper weights)
from __future__ import annotations

import wave
from pathlib import Path

import pytest


def _write_silent_wav(path: Path, *, seconds: float = 0.4, sample_rate: int = 16000) -> None:
    frames = int(sample_rate * seconds)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * frames)


def _resolve_local_whisper_choice(models_dir: Path) -> str | None:
    if (models_dir / "whisper-base" / "model.bin").exists():
        return "light"
    if (models_dir / "whisper-large-v3" / "model.bin").exists():
        return "heavy"
    return None


@pytest.mark.smoke
def test_asr_smoke_transcribe_short_wav(tmp_path):
    """
    Minimal end-to-end ASR on a tiny silent WAV.
    Skips when local Whisper weights are absent (typical CI).
    Forces CPU to avoid GPU dependency in smoke runs.
    """
    from app.config import settings

    model_choice = _resolve_local_whisper_choice(Path(settings.MODELS_DIR))
    if model_choice is None:
        pytest.skip("No local Whisper model.bin under data/models/whisper-*")

    wav_path = tmp_path / "smoke_silent.wav"
    _write_silent_wav(wav_path)

    from app import asr_core

    result = asr_core.process(
        str(wav_path),
        model_name=model_choice,
        enhance=False,
        enhance_mode="off",
        diarize=False,
        punctuate=False,
        summary_mode="off",
        device_sel="cpu",
        compute_sel="int8_float32",
    )
    assert isinstance(result, dict)
    assert not result.get("error"), result.get("error")
    assert "text" in result
    assert isinstance(result["text"], str)
