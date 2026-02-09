# api.py — نقطة دخول واجهة Arabic ASR API
import asyncio
import logging
import os
import sys
import time
import uuid
import warnings
from contextlib import asynccontextmanager
from pathlib import Path as _Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from config import settings
from server.responses import request_id_var, response_error as _response_error_for_middleware
from server.deps import get_core, set_limiter

# ——— تحذيرات طرف ثالث (بدون تغيير sys.stdout؛ مناسب لـ FastAPI و multi-workers) ———
warnings.filterwarnings("ignore", message=".*torchvision.*")
warnings.filterwarnings("ignore", message=".*cannot save figures.*")
warnings.filterwarnings("ignore", message=".*torchvision is not available.*")
warnings.filterwarnings("ignore", category=UserWarning, message=".*TypedStorage is deprecated.*")
warnings.filterwarnings("ignore", category=FutureWarning, message=".*TypedStorage is deprecated.*")
warnings.filterwarnings("ignore", message="You are using the default legacy behaviour of the <class 'transformers.models.t5.tokenization_t5.T5Tokenizer'>")
warnings.filterwarnings("ignore", message="The sentencepiece tokenizer that you are converting to a fast tokenizer uses the byte fallback option.*")
warnings.filterwarnings("ignore", category=UserWarning, message=".*pkg_resources is deprecated as an API.*")
warnings.filterwarnings("ignore", category=UserWarning, message=".*torchaudio._backend.set_audio_backend has been deprecated.*")
warnings.filterwarnings("ignore", category=UserWarning, message=".*torchaudio.backend.common.AudioMetaData.*")
warnings.filterwarnings("ignore", message=".*deprecated.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*symlinks on Windows.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*legacy behaviour of the <class 'transformers.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*torchvision is not available.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*cannot save figures.*", category=UserWarning)
if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

os.makedirs("data/logs", exist_ok=True)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.WARNING),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler("data/logs/server.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("asr_api")
# تخفيض ضجيج سجلات الطرف الثالث (بدون المساس بـ sys.stdout/stderr — ASGI-safe)
_noisy_loggers = [
    "speechbrain", "speechbrain.utils.checkpoints", "pyannote",
    "huggingface_hub", "transformers", "httpx", "urllib3",
    "torch", "torchaudio",
]
for name in _noisy_loggers:
    log = logging.getLogger(name)
    log.handlers.clear()
    log.propagate = False
    log.setLevel(logging.WARNING)
app = FastAPI(title="Arabic ASR API", version="0.1.2")

# Lifespan replaces deprecated on_event("startup")
@asynccontextmanager
async def _lifespan(app: FastAPI):
    """
    دورة حياة التطبيق. حاليًا لا يتم التحميل المسبق حسب الطلب.
    يمكن إضافة منطق التحميل المسبق هنا إذا تغيرت المتطلبات.
    """
    if settings.ASR_WARMUP:
        try:
            _ = get_core()
        except Exception as e:
            logger.warning("warmup skipped: %s", e)

    # P2-3: cleanup old output files on startup and run periodically
    cleanup_task = None
    if getattr(settings, "CLEANUP_ENABLED", True):
        try:
            from server.cleanup import cleanup_old_outputs
            cleanup_old_outputs()
        except Exception as e:
            logger.warning("startup cleanup skipped: %s", e)
        interval_sec = max(3600, int(getattr(settings, "CLEANUP_INTERVAL_HOURS", 24) * 3600))

        async def _periodic_cleanup():
            while True:
                await asyncio.sleep(interval_sec)
                try:
                    from server.cleanup import cleanup_old_outputs
                    cleanup_old_outputs()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.warning("periodic cleanup: %s", e)

        cleanup_task = asyncio.create_task(_periodic_cleanup())

    yield

    if cleanup_task is not None:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass

app.router.lifespan_context = _lifespan
if _Path("static").exists():
    app.mount("/static", StaticFiles(directory="static", html=False), name="static")

allow = settings.ASR_ALLOWED_ORIGINS.split(",") if settings.ASR_ALLOWED_ORIGINS else []
app.add_middleware(CORSMiddleware, allow_origins=allow or ["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=1024)

# حدّ حجم الطلب قبل الكتابة على القرص
class _LimitUploadSize(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        request_id_var.set(rid)
        request.state.request_id = rid
        t0 = time.time()
        cl = request.headers.get("content-length")
        ip = request.client.host if request.client else ""
        try:
            if cl and float(cl) > settings.MAX_UPLOAD_MB * 1024 * 1024:
                resp = _response_error_for_middleware(413, "file_too_large", f"max={settings.MAX_UPLOAD_MB}MB")
                resp.headers["x-request-id"] = rid
                return resp
        except Exception:
            pass
        resp = await call_next(request)
        resp.headers["x-request-id"] = rid
        resp.headers["x-runtime-ms"] = str(int((time.time() - t0)*1000))
        try:
            logger.info(
                f"rid={rid} ip={ip} cl={cl or ''} method={request.method} "
                f"path={request.url.path} status={resp.status_code} "
                f"runtime_ms={resp.headers.get('x-runtime-ms','')}"
            )
        except Exception:
            pass
        return resp
    
app.add_middleware(_LimitUploadSize)

@app.get("/robots.txt")
def robots():
    body = "User-agent: *\nDisallow:\n"
    return PlainTextResponse(body, media_type="text/plain")

@app.get("/favicon.ico")
def favicon():
    icon = _Path("static") / "favicon.ico"
    if icon.exists():
        return FileResponse(icon.as_posix(), media_type="image/x-icon", filename="favicon.ico")
    return PlainTextResponse("", status_code=204)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, lambda r, e: _response_error_for_middleware(429, "rate_limited", "too many requests"))
app.add_middleware(SlowAPIMiddleware)
set_limiter(limiter)

@app.middleware("http")
async def add_process_time_header(request, call_next):
    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = "10/minute"
    return response

from routers import health, transcribe, summarize, nlp, speakers, export, models, jobs, tts
app.include_router(health.router)
app.include_router(transcribe.router)
app.include_router(summarize.router)
app.include_router(nlp.router)
app.include_router(speakers.router)
app.include_router(export.router)
app.include_router(models.router)
app.include_router(jobs.router)
app.include_router(tts.router)

