# routers/health.py
import pathlib
import subprocess
import platform

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app import nlp_core
from app.config import settings
from app.server.deps import get_core, limiter

router = APIRouter()


def _health_ffmpeg() -> bool:
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        return True
    except Exception:
        return False


def _health_diarization(core) -> tuple:
    """Returns (available: bool, reason: str)."""
    try:
        from app.asr import diarization as _dm
        if not getattr(_dm, "_PYANNOTE_AVAILABLE", False):
            return False, "pyannote not installed"
        pipe = getattr(_dm, "_PYANNOTE_PIPELINE", None)
        if pipe is not None:
            return True, "loaded"
        return False, "pipeline not loaded (lazy or failed)"
    except Exception as e:
        return False, str(e)


def _health_tts() -> tuple:
    """Returns (ok: bool, reason: str). TTS ok if module imports (no heavy model load)."""
    try:
        from app import tts_core
        if hasattr(tts_core, "get_tts_core"):
            return True, "available"
        return False, "get_tts_core missing"
    except ImportError as e:
        return False, f"tts_core not installed: {e}"
    except Exception as e:
        return False, str(e)


@router.get("/health")
@limiter.limit("10/minute")
def health(request: Request):
    ffmpeg_ok = _health_ffmpeg()
    gpu_name = ""
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
    except Exception:
        pass
    device_mode = "cuda" if gpu_name else "cpu"

    tts_ok, tts_reason = _health_tts()
    try:
        core = get_core()
        whisper_loaded = True
        diarization_available, diarization_reason = _health_diarization(core)
        default_model = getattr(core, "DEFAULT_MODEL", settings.WHISPER_MODEL)
        return {
            "status": "ok",
            "asr_model": "ok",
            "whisper_loaded": whisper_loaded,
            "whisper_model_default": default_model,
            "model_default": default_model,
            "diarization_enabled": diarization_available,
            "diarization_available": diarization_available,
            "diarization_reason": diarization_reason,
            "tts_ok": tts_ok,
            "tts_reason": tts_reason,
            "ffmpeg_ok": ffmpeg_ok,
            "device_mode": device_mode,
            "gpu_name": gpu_name or None,
            "cuda": getattr(core, "_HAS_CUDA", False),
            "enhance_modes": ["off", "light", "full"],
            "ollama_enabled": False,
            "data_dir": str(settings.OUTPUTS_DIR.parent),
            "max_upload_mb": settings.MAX_UPLOAD_MB,
            "allowed_ext": sorted(list(settings.ALLOWED_EXT)),
            "versions": {
                "python": platform.python_version(),
                "transformers": nlp_core.get_transformers_version(),
            },
        }
    except Exception as e:
        return {
            "status": "degraded",
            "detail": str(e),
            "asr_model": "unavailable",
            "whisper_loaded": False,
            "whisper_model_default": settings.WHISPER_MODEL,
            "model_default": settings.WHISPER_MODEL,
            "diarization_enabled": False,
            "diarization_available": False,
            "diarization_reason": "core not loaded",
            "tts_ok": tts_ok,
            "tts_reason": tts_reason,
            "ffmpeg_ok": ffmpeg_ok,
            "device_mode": device_mode,
            "gpu_name": gpu_name or None,
            "cuda": False,
            "enhance_modes": ["off", "light", "full"],
            "ollama_enabled": False,
            "data_dir": str(settings.OUTPUTS_DIR.parent),
            "max_upload_mb": settings.MAX_UPLOAD_MB,
            "allowed_ext": sorted(list(settings.ALLOWED_EXT)),
            "versions": {
                "python": platform.python_version(),
                "transformers": nlp_core.get_transformers_version(),
            },
        }


@router.get("/rag-health")
def rag_health():
    rag_dir = settings.RAG_DIR
    idx = rag_dir / "index.faiss"
    docs = rag_dir / "docs.jsonl"
    raw = rag_dir / "raw.jsonl"
    exists = {
        "dir": rag_dir.as_posix(),
        "index_exists": idx.exists(),
        "docs_exists": docs.exists(),
        "raw_exists": raw.exists(),
    }

    def _stat(p: pathlib.Path):
        if not p.exists():
            return None
        try:
            s = p.stat()
            return {"size_bytes": s.st_size, "mtime": s.st_mtime}
        except Exception:
            return None

    info = {"index": _stat(idx), "docs": _stat(docs), "raw": _stat(raw)}
    line_count = None
    if docs.exists():
        try:
            with open(docs, "r", encoding="utf-8", errors="ignore") as f:
                line_count = sum(1 for _ in f)
        except Exception:
            line_count = None

    faiss_ok = None
    faiss_nt = None
    from app.nlp_core import _FAISS_OK, faiss as faiss_mod
    if _FAISS_OK and idx.exists():
        try:
            index = faiss_mod.read_index(idx.as_posix())
            faiss_ok = True
            try:
                faiss_nt = int(index.ntotal)
            except Exception:
                faiss_nt = None
        except Exception:
            faiss_ok = False
    else:
        faiss_ok = None

    return JSONResponse({
        "status": "ok" if exists["index_exists"] and exists["docs_exists"] else "missing",
        "paths": exists,
        "stats": info,
        "docs_lines": line_count,
        "faiss_loaded": faiss_ok,
        "faiss_ntotal": faiss_nt,
    })


@router.get("/jais-health")
@router.get("/ultra-health")  # توافق قديم
def jais_health():
    return {
        "engine": "jais2",
        "model": settings.JAIS_MODEL,
        "jais_4bit": settings.JAIS_4BIT,
        "trust_remote": settings.JAIS_TRUST_REMOTE,
        "prompt_mode": settings.JAIS_PROMPT_MODE,
    }
