# asr/__init__.py — نقطة دخول حزمة ASR (logging + warnings فقط؛ لا استبدال sys.stdout/stderr — ASGI-safe)
import os
import logging
import warnings

warnings.filterwarnings("ignore", message=".*torchaudio.backend.common.AudioMetaData.*")
warnings.filterwarnings("ignore", message=".*torchaudio._backend.*")
warnings.filterwarnings("ignore", message=".*deprecated.*")
warnings.filterwarnings("ignore", message=".*torchvision.*")
warnings.filterwarnings("ignore", message=".*cannot save figures.*")
# تخفيض ضجيج السجلات بدل اعتراض stdout
for _name in ("torch", "torchaudio"):
    _log = logging.getLogger(_name)
    _log.setLevel(logging.WARNING)
    _log.propagate = False
    _log.handlers.clear()
logging.getLogger("pyannote").setLevel(logging.ERROR)
logging.getLogger("pyannote").propagate = False

import torch
from app.config import settings

from . import common
from .common import setup_env, OUTPUTS_DIR, MODELS_DIR, SPK_DIR, DEFAULT_MODEL, MODEL_CHOICES

setup_env(torch)
_HAS_CUDA = torch.cuda.is_available()
if _HAS_CUDA and hasattr(torch, "set_float32_matmul_precision"):
    torch.set_float32_matmul_precision("high")

OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)
SPK_DIR.mkdir(parents=True, exist_ok=True)

from . import whisper as whisper_mod
from . import diarization as diarization_mod
from . import speakers as speakers_mod

whisper_mod.init_whisper(_HAS_CUDA, MODELS_DIR, settings.HF_TOKEN)
diarization_mod.init_diarization(settings.HF_TOKEN, _HAS_CUDA)
speakers_mod.init_speakers(MODELS_DIR, SPK_DIR, settings.HF_TOKEN)

from .common import (
    speaker_label as _speaker_label,
    to_ar_speaker as _to_ar_speaker,
    err as _err,
    tmp_wav as _tmp_wav,
    safe_filename as _safe_filename,
    resolve_model as _resolve_model,
    safe_compute as _safe_compute,
)
from .audio import (
    wav_read_mono as _wav_read_mono,
    to_wav16k,
    enhance_audio,
    to_wav16k_enhanced,
)
from .whisper import get_model, run_asr
from .diarization import (
    diarize_with_pyannote,
    map_speakers_to_segments as _map_speakers_to_segments,
)
from .speakers import (
    get_spkrec,
    load_enrolled,
    get_speaker_files,
    delete_speaker,
    enroll_voice,
    map_generic_to_enrolled_speakers as _map_generic_to_enrolled_speakers,
)
from .subtitles import segments_to_srt, segments_to_vtt
from .process import process, process_many, cleanup_temp_files

# للتوافق مع asr_core: أسماء يُتوقعها المستدعون
_PYANNOTE_AVAILABLE = getattr(diarization_mod, "_PYANNOTE_AVAILABLE", False)

__all__ = [
    "DEFAULT_MODEL",
    "MODEL_CHOICES",
    "OUTPUTS_DIR",
    "MODELS_DIR",
    "SPK_DIR",
    "_HAS_CUDA",
    "get_model",
    "run_asr",
    "diarize_with_pyannote",
    "load_enrolled",
    "get_speaker_files",
    "delete_speaker",
    "enroll_voice",
    "segments_to_srt",
    "segments_to_vtt",
    "process",
    "process_many",
    "cleanup_temp_files",
    "to_wav16k",
    "to_wav16k_enhanced",
    "enhance_audio",
]
