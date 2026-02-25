# tts_mms.py — Arabic TTS using facebook/mms-tts-ara (Transformers VITS)
"""Offline Arabic TTS. Uses facebook/mms-tts-ara. No extra deps — transformers + torch already in project."""

import logging
import pathlib
from typing import Optional

from app.config import settings

logger = logging.getLogger("tts_mms")

MMS_MODEL_ID = "facebook/mms-tts-ara"
_MMS_MODEL = None
_MMS_TOKENIZER = None


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
        _MMS_TOKENIZER = AutoTokenizer.from_pretrained(MMS_MODEL_ID)
        _MMS_MODEL = VitsModel.from_pretrained(MMS_MODEL_ID)
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

    import torch
    if seed is not None:
        torch.manual_seed(int(seed))
    inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=512)
    if torch.cuda.is_available():
        inputs = {k: v.cuda() for k, v in inputs.items()}

    with torch.no_grad():
        output = model(**inputs).waveform

    # output: [1, samples], float32 in [-1,1]
    waveform = output.squeeze().cpu().numpy()
    sample_rate = model.config.sampling_rate

    import soundfile as sf
    sf.write(out_path, waveform, sample_rate)

    duration_sec = len(waveform) / float(sample_rate)
    return {
        "audio_path": out_path,
        "sample_rate": sample_rate,
        "duration_sec": round(duration_sec, 3),
        "voice": "ar_mms",
    }
