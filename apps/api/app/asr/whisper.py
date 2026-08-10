# asr/whisper.py — تحميل وتشغيل نموذج Whisper
from typing import Optional, Dict, List

from huggingface_hub import snapshot_download
from faster_whisper import WhisperModel

from app.config import settings
from app.infrastructure.download_retry import run_with_download_retry
from .common import resolve_model, safe_compute

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


def unload_whisper_models() -> int:
    """حرّر نماذج Whisper من الذاكرة (خصوصاً VRAM) قبل تحميل نموذج التلخيص."""
    n = len(_MODEL_CACHE)
    _MODEL_CACHE.clear()
    if n:
        print(f"[WHISPER] unloaded {n} cached model(s)")
    return n


def get_model(name: str, device: Optional[str] = None, compute_type: Optional[str] = None) -> WhisperModel:
    name = resolve_model(name)
    dev, ctp = safe_compute(device, compute_type, _HAS_CUDA)
    key = (name, dev, ctp)
    if key in _MODEL_CACHE:
        return _MODEL_CACHE[key]

    # حرّر VRAM من Jais قبل تحميل Whisper (كرت 6–8GB لا يتحمل الاثنين معاً)
    try:
        from app.nlp.summarization import unload_summarizer_pipes

        unload_summarizer_pipes("jais")
    except Exception:
        pass

    local_dir = MODELS_DIR / f"whisper-{name}"
    # Require model.bin so a partial HF download is not treated as "already local"
    if not (local_dir / "model.bin").exists():
        def _download_once():
            return snapshot_download(
                repo_id=f"Systran/faster-whisper-{name}",
                local_dir=str(local_dir),
                local_dir_use_symlinks=False,
                cache_dir=str(settings.HF_DIR),
                token=_HF_TOKEN,
            )

        run_with_download_retry(_download_once, f"asr:whisper-{name}")

    # On CUDA OOM, fall back: float16 → int8 → cpu/int8_float32
    attempts = [(dev, ctp)]
    if dev == "cuda":
        if ctp != "int8":
            attempts.append((dev, "int8"))
        attempts.append(("cpu", "int8_float32"))

    last_error: Optional[Exception] = None
    for attempt_dev, attempt_ctp in attempts:
        attempt_key = (name, attempt_dev, attempt_ctp)
        if attempt_key in _MODEL_CACHE:
            return _MODEL_CACHE[attempt_key]
        try:
            model_args = {
                "device": attempt_dev,
                "compute_type": attempt_ctp,
                "cpu_threads": settings.CPU_THREADS,
                "download_root": str(MODELS_DIR),
            }
            if attempt_dev == "cuda":
                model_args["device_index"] = settings.GPU_ID
            model = WhisperModel(str(local_dir), **model_args)
            _MODEL_CACHE[attempt_key] = model
            # Also cache under the originally requested key so callers reuse the working load.
            _MODEL_CACHE[key] = model
            if settings.ASR_LOG_LOAD or (attempt_dev, attempt_ctp) != (dev, ctp):
                print(
                    f"[WHISPER] loaded name={name} path={local_dir} "
                    f"device={attempt_dev} compute={attempt_ctp}"
                    + (f" (fallback from {dev}/{ctp})" if (attempt_dev, attempt_ctp) != (dev, ctp) else "")
                )
            return model
        except Exception as e:
            last_error = e
            err_l = str(e).lower()
            is_oom = "out of memory" in err_l or "cuda" in err_l and "memory" in err_l
            if not is_oom:
                break
            print(f"[WHISPER] load failed ({attempt_dev}/{attempt_ctp}): {e} — trying fallback...")
            continue

    raise RuntimeError(f"Failed to load Whisper model {name}: {last_error}") from last_error


def run_asr(
    wav_path: str,
    model_obj: WhisperModel,
    whisper_mode: str = "normal",
    multi_speaker: bool = False,
):
    if whisper_mode == "whisper":
        init_prompt = (
            "حوار باللهجة السورية العامية، نص واضح ودقيق. "
            "مصطلحات: تلخيص، تفريغ صوتي، ذكاء اصطناعي، دون اتصال بالإنترنت، محضر اجتماع."
        )
    else:
        init_prompt = (
            "نص عربي فصيح واضح مع علامات ترقيم مناسبة. "
            "مصطلحات: تلخيص، تفريغ صوتي، ذكاء اصطناعي، دون اتصال بالإنترنت، محضر اجتماع."
        )
    segments_generator, info = model_obj.transcribe(
        wav_path,
        language="ar",
        task="transcribe",
        vad_filter=True,
        vad_parameters={
            "threshold": 0.45,
            "min_silence_duration_ms": 400,
            "speech_pad_ms": 200,
        },
        beam_size=8,
        temperature=[0.0, 0.2, 0.4],
        compression_ratio_threshold=2.4,
        log_prob_threshold=-1.0,
        no_speech_threshold=0.5,
        condition_on_previous_text=not multi_speaker,
        initial_prompt=init_prompt,
    )
    seglist = [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments_generator]
    meta = f"المدة: {info.duration:.1f}s | اللغة: {info.language} | ثقة: {info.language_probability:.2f}"
    return meta, seglist
