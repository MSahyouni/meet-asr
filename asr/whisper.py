# asr/whisper.py — تحميل وتشغيل نموذج Whisper
from typing import Optional, Dict, List

from huggingface_hub import snapshot_download
from faster_whisper import WhisperModel

from config import settings
from asr.common import resolve_model, safe_compute

# يُملأ من asr/__init__ بعد تعريف _HAS_CUDA, MODELS_DIR, _HF_TOKEN
_MODEL_CACHE: Dict = {}
_HAS_CUDA = False
MODELS_DIR = None
_HF_TOKEN = None


def init_whisper(has_cuda: bool, models_dir, hf_token):
    global _HAS_CUDA, MODELS_DIR, _HF_TOKEN
    _HAS_CUDA = has_cuda
    MODELS_DIR = models_dir
    _HF_TOKEN = hf_token


def get_model(name: str, device: Optional[str] = None, compute_type: Optional[str] = None) -> WhisperModel:
    name = resolve_model(name)
    dev, ctp = safe_compute(device, compute_type, _HAS_CUDA)
    key = (name, dev, ctp)
    if key not in _MODEL_CACHE:
        try:
            local_dir = MODELS_DIR / f"whisper-{name}"
            if not local_dir.exists():
                snapshot_download(
                    repo_id=f"Systran/faster-whisper-{name}",
                    local_dir=str(local_dir),
                    local_dir_use_symlinks=False,
                    cache_dir=str(settings.HF_DIR),
                    token=_HF_TOKEN,
                )
            model_args = {
                "device": dev,
                "compute_type": ctp,
                "cpu_threads": settings.CPU_THREADS,
                "download_root": str(MODELS_DIR),
            }
            if dev == "cuda":
                model_args["device_index"] = settings.GPU_ID
            _MODEL_CACHE[key] = WhisperModel(str(local_dir), **model_args)
            if settings.ASR_LOG_LOAD:
                print(f"[WHISPER] loaded name={name} path={local_dir} device={dev} compute={ctp}")
        except Exception as e:
            raise RuntimeError(f"Failed to load Whisper model {name}: {e}") from e
    return _MODEL_CACHE[key]


def run_asr(wav_path: str, model_obj: WhisperModel, whisper_mode: str = "normal"):
    init_prompt = "لغة عربية عامية سورية." if whisper_mode == "whisper" else "لغة عربية فصحى."
    segments_generator, info = model_obj.transcribe(
        wav_path,
        language="ar",
        task="transcribe",
        vad_filter=True,
        vad_parameters={"threshold": 0.7, "min_silence_duration_ms": 800, "speech_pad_ms": 100},
        beam_size=5,
        temperature=[0.0, 0.2, 0.4],
        initial_prompt=init_prompt,
    )
    seglist = [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments_generator]
    meta = f"المدة: {info.duration:.1f}s | اللغة: {info.language} | ثقة: {info.language_probability:.2f}"
    return meta, seglist
