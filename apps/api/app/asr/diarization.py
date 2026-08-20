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

from .common import speaker_label, to_ar_speaker, speaker_id_from_label, ensure_segment_speaker_id
from app.infrastructure.download_retry import run_with_download_retry

_HF_TOKEN = None
_HAS_CUDA = False
_PYANNOTE_PIPELINE = None


def init_diarization(hf_token, has_cuda: bool):
    global _HF_TOKEN, _HAS_CUDA
    _HF_TOKEN = hf_token
    _HAS_CUDA = has_cuda


def unload_diarization_pipeline() -> bool:
    """أنزل pipeline البايانوت من GPU/الذاكرة قبل مراحل NLP الثقيلة."""
    global _PYANNOTE_PIPELINE
    if _PYANNOTE_PIPELINE is None:
        return False
    try:
        del _PYANNOTE_PIPELINE
    except Exception:
        pass
    _PYANNOTE_PIPELINE = None
    print("[PYANNOTE] pipeline unloaded")
    return True


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
        if not (_HF_TOKEN or "").strip():
            log.warning(
                "Diarization skipped: HF_TOKEN غير مضبوط. "
                "أنشئ توكن من https://hf.co/settings/tokens واقبل شروط "
                "pyannote/speaker-diarization-3.1 و pyannote/segmentation-3.0 ثم ضع HF_TOKEN في apps/api/.env وأعد تشغيل السيرفر."
            )
            return None
        log.info("Loading diarization pipeline...")
        # token= is the current huggingface_hub API; use_auth_token kept as fallback for older pyannote.
        def _from_pretrained():
            try:
                return Pipeline.from_pretrained(
                    "pyannote/speaker-diarization-3.1",
                    token=_HF_TOKEN,
                )
            except TypeError:
                return Pipeline.from_pretrained(
                    "pyannote/speaker-diarization-3.1",
                    use_auth_token=_HF_TOKEN,
                )

        pipeline = run_with_download_retry(_from_pretrained, "asr:pyannote-diarization", max_attempts=3)
        if pipeline is None:
            raise RuntimeError(
                "Pipeline.from_pretrained أعاد None — غالباً النموذج gated ولم يُقبل بعد، "
                "أو التوكن بلا صلاحية قراءة. اقبل الشروط على Hugging Face ثم أعد المحاولة."
            )
        if _HAS_CUDA:
            pipeline.to(torch.device("cuda"))
        _PYANNOTE_PIPELINE = pipeline
        log.info("Diarization pipeline loaded.")
        return _PYANNOTE_PIPELINE
    except Exception as e:
        import logging
        msg = str(e)
        lowered = msg.lower()
        if "gated" in lowered or "403" in lowered or "public gated repositories" in lowered:
            tip = (
                " توكن Hugging Face يحتاج صلاحية Access to public gated repositories، "
                "واقبل شروط pyannote/speaker-diarization-3.1 و pyannote/segmentation-3.0 ثم أعد تشغيل السيرفر."
            )
            msg = f"{msg}{tip}"
        elif "connection" in lowered or "local cache" in lowered:
            tip = (
                " غالباً رفض صلاحيات (403 على نموذج gated) وليس انقطاع الشبكة. "
                "فعّل Access to public gated repositories في إعدادات التوكن، أو استخدم classic read token."
            )
            msg = f"{msg}{tip}"
        logging.getLogger("asr.diarization").warning("Diarization pipeline disabled: %s", msg)
        _PYANNOTE_PIPELINE = None
        return None


def diarize_with_pyannote(
    wav_path: str,
    num_speakers: int = 0,
    *,
    min_speakers: int = 0,
    max_speakers: int = 0,
) -> List[Dict]:
    print(f"[PYANNOTE] بدء تنفيذ diarize_with_pyannote على الملف: {wav_path}")
    pipeline = _load_pyannote_pipeline()
    if not pipeline:
        print("[PYANNOTE] Pipeline not loaded: تحقق من التوكن أو الاتصال أو تثبيت pyannote.audio.")
        return []
    try:
        params = {}
        if num_speakers > 0:
            params["num_speakers"] = int(num_speakers)
        else:
            # Unconstrained auto often collapses short meetings to 1 speaker.
            if min_speakers > 0:
                params["min_speakers"] = int(min_speakers)
            if max_speakers > 0:
                params["max_speakers"] = int(max_speakers)
        print(f"[PYANNOTE] params={params or 'auto'}")
        diarization = pipeline(wav_path, **params)
        results = [
            {"start": turn.start, "end": turn.end, "speaker": speaker}
            for turn, _, speaker in diarization.itertracks(yield_label=True)
        ]
        uniq = sorted({r["speaker"] for r in results})
        print(f"[PYANNOTE] عدد المقاطع={len(results)} المتكلمون={uniq}")
        return results
    except Exception as e:
        print(f"[PYANNOTE] Diarization failed: {e}")
        return []


def pyannote_speaker_params(*, auto_k: bool, max_speakers: int) -> dict:
    """Build diarize_with_pyannote kwargs from UI auto_k / max_speakers."""
    cap = max(1, int(max_speakers or 2))
    if not auto_k:
        return {"num_speakers": cap}
    # Prefer at least 2 speakers when the UI allows it — pure auto often returns K=1
    # on single-mic meetings even when a second person speaks briefly.
    floor = 2 if cap >= 2 else 1
    return {"num_speakers": 0, "min_speakers": floor, "max_speakers": cap}


def map_speakers_to_segments(whisper_segments: List[Dict], speaker_turns: List[Dict]) -> List[Dict]:
    if not speaker_turns:
        for seg in whisper_segments:
            seg["speaker_id"] = "spk_00"
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
        raw_label = max(overlap, key=overlap.get) if overlap else "SPEAKER_00"
        seg["speaker_id"] = speaker_id_from_label(raw_label)
        seg["speaker"] = to_ar_speaker(raw_label)
        ensure_segment_speaker_id(seg)
    return whisper_segments



