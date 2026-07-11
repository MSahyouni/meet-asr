# tts_mms.py — Arabic TTS using facebook/mms-tts-ara (Transformers VITS)
"""Offline Arabic TTS. Uses facebook/mms-tts-ara. No extra deps — transformers + torch already in project."""

import logging
import pathlib
from typing import Optional

from app.config import settings
from app.infrastructure.download_retry import run_with_download_retry

logger = logging.getLogger("tts_mms")

MMS_MODEL_ID = "facebook/mms-tts-ara"
_MMS_MODEL = None
_MMS_TOKENIZER = None


from app.tts.audio_speed import apply_speed_numpy


def _get_mms():
    """Lazy-load MMS-TTS model (singleton)."""
    global _MMS_MODEL, _MMS_TOKENIZER
    if _MMS_MODEL is not None:
        return _MMS_MODEL, _MMS_TOKENIZER
    import os
    os.environ.setdefault("HF_HOME", str(settings.HF_DIR))
    try:
        from transformers import VitsModel, AutoTokenizer
        import torch
        logger.info("Loading MMS-TTS Arabic (first run may download ~200MB)...")
        _MMS_TOKENIZER = run_with_download_retry(
            lambda: AutoTokenizer.from_pretrained(MMS_MODEL_ID),
            "tts:mms-tokenizer",
        )
        _MMS_MODEL = run_with_download_retry(
            lambda: VitsModel.from_pretrained(MMS_MODEL_ID),
            "tts:mms-model",
        )
        _MMS_MODEL.eval()
        if torch.cuda.is_available():
            _MMS_MODEL = _MMS_MODEL.cuda()
        logger.info("MMS-TTS Arabic loaded.")
        return _MMS_MODEL, _MMS_TOKENIZER
    except ImportError as e:
        raise RuntimeError("MMS-TTS requires transformers>=4.33. Install: pip install transformers") from e
    except Exception as e:
        logger.exception("Failed to load MMS-TTS: %s", e)
        raise RuntimeError(f"Failed to load MMS-TTS: {e}") from e


def synthesize_mms(
    text: str,
    voice: str = "",
    speed: float = 1.0,
    out_path: str = "",
    seed: Optional[int] = None,
) -> dict:
    """
    Synthesize Arabic text using facebook/mms-tts-ara.
    voice: ar_mms (single voice; ignored for compatibility).
    seed: optional int for reproducible rhythm variation (same voice, different timing).
    """
    model, tokenizer = _get_mms()
    out_dir = pathlib.Path(settings.OUTPUTS_DIR) / "tts"
    out_dir.mkdir(parents=True, exist_ok=True)
    if not out_path or not pathlib.Path(out_path).suffix:
        import time
        base = f"mms_{int(time.time() * 1000)}"
        out_path = str(out_dir / f"{base}.wav")
    else:
        p = pathlib.Path(out_path)
        if not p.is_absolute():
            p = out_dir / p.name
        p.parent.mkdir(parents=True, exist_ok=True)
        out_path = str(p.resolve())

    from app.tts.text_utils import split_text_for_tts

    import torch
    if seed is not None:
        torch.manual_seed(int(seed))

    chunks = split_text_for_tts(text, max_chunk_chars=220)
    if not chunks:
        chunks = [text]

    audio_parts = []
    silence_cache = {}
    for chunk in chunks:
        inputs = tokenizer(chunk, return_tensors="pt", padding=True, truncation=True, max_length=512)
        if "input_ids" in inputs:
            inputs["input_ids"] = inputs["input_ids"].long()
        if "attention_mask" in inputs:
            inputs["attention_mask"] = inputs["attention_mask"].long()
        if "token_type_ids" in inputs:
            inputs["token_type_ids"] = inputs["token_type_ids"].long()
        if torch.cuda.is_available():
            inputs = {k: v.cuda() for k, v in inputs.items()}

        with torch.no_grad():
            output = model(**inputs).waveform

        wav = output.squeeze().cpu().numpy()
        audio_parts.append(wav)

        end_mark = chunk[-1] if chunk else ""
        pause_sec = 0.08 if end_mark in ("،", ";", "؛", ":") else 0.14
        silence_cache.setdefault(pause_sec, (pause_sec, None))
        audio_parts.append(("__silence__", pause_sec))

    sample_rate = model.config.sampling_rate
    import numpy as np
    final_parts = []
    for part in audio_parts:
        if isinstance(part, tuple) and part and part[0] == "__silence__":
            pause_sec = float(part[1])
            num_samples = max(1, int(sample_rate * pause_sec))
            final_parts.append(np.zeros(num_samples, dtype=np.float32))
            continue
        final_parts.append(np.asarray(part, dtype=np.float32))

    if final_parts:
        waveform = np.concatenate(final_parts, axis=0)
    else:
        waveform = np.zeros(1, dtype=np.float32)

    waveform = apply_speed_numpy(waveform, speed)
    sample_rate = model.config.sampling_rate

    import soundfile as sf
    sf.write(out_path, waveform, sample_rate)

    duration_sec = len(waveform) / float(sample_rate)
    return {
        "audio_path": out_path,
        "sample_rate": sample_rate,
        "duration_sec": round(duration_sec, 3),
        "voice": "ar_mms",
        "chunks_count": len(chunks),
    }
