# asr/diarization.py — Pyannote تمييز المتكلمين
import warnings
from typing import List, Dict
from collections import defaultdict

try:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*torchvision.*")
        warnings.filterwarnings("ignore", message=".*cannot save figures.*")
        from pyannote.audio import Pipeline
    _PYANNOTE_AVAILABLE = True
except ImportError:
    _PYANNOTE_AVAILABLE = False
    Pipeline = None

from asr.common import speaker_label, to_ar_speaker

_HF_TOKEN = None
_HAS_CUDA = False
_PYANNOTE_PIPELINE = None


def init_diarization(hf_token, has_cuda: bool):
    global _HF_TOKEN, _HAS_CUDA
    _HF_TOKEN = hf_token
    _HAS_CUDA = has_cuda


def _load_pyannote_pipeline():
    global _PYANNOTE_PIPELINE
    if not _PYANNOTE_AVAILABLE:
        return None
    if _PYANNOTE_PIPELINE is not None:
        return _PYANNOTE_PIPELINE
    try:
        import torch
        import logging
        log = logging.getLogger("asr.diarization")
        log.info("Loading diarization pipeline...")
        pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", use_auth_token=_HF_TOKEN)
        if _HAS_CUDA:
            pipeline.to(torch.device("cuda"))
        _PYANNOTE_PIPELINE = pipeline
        log.info("Diarization pipeline loaded.")
        return _PYANNOTE_PIPELINE
    except Exception as e:
        import logging
        logging.getLogger("asr.diarization").warning("Diarization pipeline disabled: %s", e)
        _PYANNOTE_PIPELINE = None
        return None


def diarize_with_pyannote(wav_path: str, num_speakers: int = 0) -> List[Dict]:
    pipeline = _load_pyannote_pipeline()
    if not pipeline:
        return []
    try:
        params = {}
        if num_speakers > 0:
            params["num_speakers"] = num_speakers
        diarization = pipeline(wav_path, **params)
        return [
            {"start": turn.start, "end": turn.end, "speaker": speaker}
            for turn, _, speaker in diarization.itertracks(yield_label=True)
        ]
    except Exception as e:
        print(f"[PYANNOTE] Diarization failed: {e}")
        return []


def map_speakers_to_segments(whisper_segments: List[Dict], speaker_turns: List[Dict]) -> List[Dict]:
    if not speaker_turns:
        for seg in whisper_segments:
            seg["speaker"] = speaker_label(0)
        return whisper_segments
    for seg in whisper_segments:
        seg_start, seg_end = seg["start"], seg["end"]
        overlap = defaultdict(float)
        for turn in speaker_turns:
            turn_start, turn_end = turn["start"], turn["end"]
            o = max(0.0, min(seg_end, turn_end) - max(seg_start, turn_start))
            if o > 0:
                overlap[turn["speaker"]] += o
        ar_label = max(overlap, key=overlap.get) if overlap else speaker_label(0)
        seg["speaker"] = to_ar_speaker(ar_label)
    return whisper_segments
