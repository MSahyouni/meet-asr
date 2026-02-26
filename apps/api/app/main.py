# app/main.py — Main FastAPI Application Entry Point
"""
Main application factory for Meet‑ASR API.
Reorganized to follow MSahyouni/nlp-project architecture.
"""

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
from slowapi.middleware import SlowAPIMiddleware

from app.config import settings
from app.server.responses import request_id_var
from app.server.deps import get_core, set_limiter

# ——— Third-party warnings filter (without changing sys.stdout; suitable for FastAPI & multi-workers) ———
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

# ——— Logging Setup ———
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# ——— Request ID Context Variable ———


def _is_production_env() -> bool:
    env = (
        os.getenv("ASR_ENV")
        or os.getenv("APP_ENV")
        or os.getenv("ENV")
        or ""
    ).strip().lower()
    return env in {"prod", "production"}


def _resolve_cors_origins() -> list[str]:
    raw = (settings.ASR_ALLOWED_ORIGINS or "").strip()
    if raw:
        origins = [item.strip() for item in raw.split(",") if item.strip()]
        if origins:
            if _is_production_env() and "*" in origins:
                raise RuntimeError("ASR_ALLOWED_ORIGINS must be explicit in production (wildcard is not allowed)")
            return origins
    if _is_production_env():
        raise RuntimeError("ASR_ALLOWED_ORIGINS must be configured in production")
    return ["*"]


class MergedRequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = str(uuid.uuid4())
        request_id_var.set(rid)
        start_time = time.time()
        try:
            response = await call_next(request)
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            logging.error(f"[{rid}] Unhandled exception | path={request.url.path} | elapsed={elapsed:.0f}ms", exc_info=True)
            raise
        elapsed = (time.time() - start_time) * 1000
        logging.debug(f"[{rid}] Request complete | method={request.method} | path={request.url.path} | status={response.status_code} | elapsed={elapsed:.0f}ms")
        return response


# ——— Static Files ———
_project_root = _Path(__file__).resolve().parent.parent.parent.parent
_static_dir = _project_root / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logging.info("Application startup")
    try:
        core = get_core()
        logging.info("Core services initialized")
    except Exception as e:
        logging.error(f"Failed to initialize core: {e}")
    yield
    # Shutdown
    logging.info("Application shutting down")


# ——— FastAPI App ———
app = FastAPI(
    title="Meet-ASR API",
    description="Arabic Speech Recognition with Diarization, Summarization, and TTS",
    version="1.0.0",
    lifespan=lifespan,
)

# ——— Middleware ———
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
set_limiter(limiter)

app.add_middleware(SlowAPIMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_resolve_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(MergedRequestIdMiddleware)

# ——— Static Files ———
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


@app.get("/", tags=["Frontend"])
async def root():
    index_file = _static_dir / "frontend" / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file), media_type="text/html")
    return PlainTextResponse("Frontend not found", status_code=404)


@app.get("/favicon.png", tags=["Frontend"])
async def favicon():
    favicon_file = _static_dir / "favicon.png"
    if favicon_file.exists():
        return FileResponse(str(favicon_file), media_type="image/png")
    return PlainTextResponse("Favicon not found", status_code=404)


@app.get("/favicon.ico", tags=["Frontend"])
async def favicon_ico():
    favicon_file = _static_dir / "favicon.png"
    if favicon_file.exists():
        return FileResponse(str(favicon_file), media_type="image/png")
    return PlainTextResponse("Favicon not found", status_code=404)


# ——— Route Includes (from features) ———
from app.features.health import router as health_router
from app.features.asr import router as asr_router
from app.features.nlp import router as nlp_router
from app.features.tts import router as tts_router
from app.features.auth.router import router as auth_router
from app.features.users import router as users_router
from app.features.billing import router as billing_router
from app.features.dashboard import router as dashboard_router

app.include_router(health_router, tags=["Health"])
app.include_router(asr_router, prefix="/asr", tags=["ASR"])
app.include_router(nlp_router, prefix="/nlp", tags=["NLP"])
app.include_router(tts_router, prefix="/tts", tags=["TTS"])
app.include_router(auth_router, tags=["Auth"])
app.include_router(users_router, tags=["Users"])
app.include_router(billing_router, tags=["Billing"])
app.include_router(dashboard_router, tags=["Dashboard"])


# ——— Legacy Route Includes (from routers; for backward compatibility) ———
try:
    from app.routers import router as legacy_router
    app.include_router(legacy_router)
except ImportError:
    logging.warning("Legacy routers not found")
