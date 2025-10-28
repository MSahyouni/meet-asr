# api.py - نسخة مستقرة مُحسّنة
import tempfile, shutil, pathlib, re, traceback, secrets, json, sys, asyncio, subprocess
from typing import List, Tuple, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, Header, Request
import contextvars
import warnings
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from urllib.parse import quote
import logging
import os
import platform
import aiofiles

from config import settings

# ——— تحذيرات طرف ثالث ———
warnings.filterwarnings("ignore", category=UserWarning, message=".*TypedStorage is deprecated.*")
warnings.filterwarnings("ignore", category=FutureWarning, message=".*TypedStorage is deprecated.*")
warnings.filterwarnings("ignore", message="You are using the default legacy behaviour of the <class 'transformers.models.t5.tokenization_t5.T5Tokenizer'>")
warnings.filterwarnings("ignore", message="The sentencepiece tokenizer that you are converting to a fast tokenizer uses the byte fallback option.*")
warnings.filterwarnings("ignore", category=UserWarning, message=".*pkg_resources is deprecated as an API.*")
warnings.filterwarnings("ignore", category=UserWarning, message=".*torchaudio._backend.set_audio_backend has been deprecated.*")
warnings.filterwarnings("ignore", message=".*deprecated.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*symlinks on Windows.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*legacy behaviour of the <class 'transformers.*", category=UserWarning)
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
for name in [
    "speechbrain", "speechbrain.utils.checkpoints", "pyannote",
    "huggingface_hub", "transformers", "httpx", "urllib3"
]:
    logging.getLogger(name).handlers.clear()
    logging.getLogger(name).propagate = False
    logging.getLogger(name).setLevel(logging.WARNING)
app = FastAPI(title="Arabic ASR API", version="0.1.2")
_RID: contextvars.ContextVar[str] = contextvars.ContextVar("rid", default="")

# Lifespan replaces deprecated on_event("startup")
@asynccontextmanager
async def _lifespan(_: FastAPI):
    """
    دورة حياة التطبيق. حاليًا لا يتم التحميل المسبق حسب الطلب.
    يمكن إضافة منطق التحميل المسبق هنا إذا تغيرت المتطلبات.
    """
      # warmup اختياري لتعجيل أول طلب، نعطّله في CI
    if settings.ASR_WARMUP and os.getenv("CI") != "true":
        try:
            _ = _get_core()
        except Exception as e:
            print(f"[warmup] skipped: {e}")
    yield

app.router.lifespan_context = _lifespan
if pathlib.Path("static").exists():
    app.mount("/static", StaticFiles(directory="static", html=False), name="static")

allow = settings.ASR_ALLOWED_ORIGINS.split(",") if settings.ASR_ALLOWED_ORIGINS else []
app.add_middleware(CORSMiddleware, allow_origins=allow or ["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=1024)

# حدّ حجم الطلب قبل الكتابة على القرص

def _get_core():
    """الحصول على النواة مع استيراد كسول لتفادي فشل import في CI."""
    global _CORE
    if _CORE is not None:
        return _CORE
    try:
        # الاستيراد هنا فقط عند الحاجة
        import nlp_core  # type: ignore
    except Exception as e:
        raise RuntimeError(f"nlp_core unavailable: {e}")
    _CORE = nlp_core.get_core_singleton(settings)  # أو المُنشئ المناسب في nlp_core
    return _CORE

from starlette.middleware.base import BaseHTTPMiddleware
import uuid, time
class _LimitUploadSize(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        _RID.set(rid)
        request.state.request_id = rid
        t0 = time.time()
        cl = request.headers.get("content-length")
        ip = request.client.host if request.client else ""
        try:
            if cl and float(cl) > settings.MAX_UPLOAD_MB * 1024 * 1024:
                resp = _response_error(413, "file_too_large", f"max={settings.MAX_UPLOAD_MB}MB")
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
    icon = pathlib.Path("static") / "favicon.ico"
    if icon.exists():
        return FileResponse(icon.as_posix(), media_type="image/x-icon", filename="favicon.ico")
    return PlainTextResponse("", status_code=204)

def _get_core():
    try:
        import asr_core
        return asr_core
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"ASR core unavailable: {e}")
    
@app.delete("/delete-speaker")
def delete_speaker(name: str = Query(...), x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    if settings.API_TOKEN and not secrets.compare_digest(x_api_key or "", settings.API_TOKEN):
        return _response_error(401, "unauthorized", "invalid api key")
    core = _get_core()
    ok, msg = core.delete_speaker(name)
    return {"success": bool(ok), "message": msg}

@app.get("/speaker-files")
def speaker_files(name: str = Query(...), x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    if settings.API_TOKEN and not secrets.compare_digest(x_api_key or "", settings.API_TOKEN):
        return _response_error(401, "unauthorized", "invalid api key")
    core = _get_core()
    return {"files": core.get_speaker_files(name)}

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, lambda r, e: _response_error(429, "rate_limited", "too many requests"))
app.add_middleware(SlowAPIMiddleware)

@app.middleware("http")
async def add_process_time_header(request, call_next):
    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = "10/minute"
    return response

@app.get("/health")
@limiter.limit("10/minute")
def health(request: Request):
    try:
        core = _get_core()
        # فحص ffmpeg مبسّط
        try:
            subprocess.run(["ffmpeg","-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            ffmpeg_ok = True
        except Exception:
            ffmpeg_ok = False
        gpu_name = ""
        try:
            import torch
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
        except Exception:
            pass
        return {
            "status": "ok",
            "model_default": getattr(core, "DEFAULT_MODEL", settings.WHISPER_MODEL),
            "cuda": getattr(core, "_HAS_CUDA", False),
            "ollama_enabled": False,
            "ffmpeg": ffmpeg_ok,
            "gpu_name": gpu_name,
            "data_dir": str(settings.OUTPUTS_DIR.parent),
            "max_upload_mb": settings.MAX_UPLOAD_MB,
            "allowed_ext": sorted(list(settings.ALLOWED_EXT)),
            "versions": {
                "python": platform.python_version(),
                "transformers": nlp_core.get_transformers_version(),
            },
        }
    except Exception as e:
        gpu_name = ""
        try:
            import torch
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
        except Exception:
            pass
        return {
            "status": "degraded",
            "detail": str(e),
            "model_default": settings.WHISPER_MODEL,
            "cuda": False,
            "ollama_enabled": False,
            "ffmpeg": False,
            "gpu_name": gpu_name,
            "data_dir": str(settings.OUTPUTS_DIR.parent),
            "max_upload_mb": settings.MAX_UPLOAD_MB,
            "allowed_ext": sorted(list(settings.ALLOWED_EXT)),
            "versions": {
                "python": platform.python_version(),
                "transformers": nlp_core.get_transformers_version(),
            },
        }
    
@app.get("/rag-health")
def rag_health():
    rag_dir = settings.RAG_DIR
    idx = rag_dir / "index.faiss"
    docs = rag_dir / "docs.jsonl"
    raw  = rag_dir / "raw.jsonl"

    exists = {
        "dir": rag_dir.as_posix(),
        "index_exists": idx.exists(),
        "docs_exists": docs.exists(),
        "raw_exists": raw.exists(),
    }

    # مقاسات وتواريخ آخر تعديل (إن وجدت)
    def _stat(p: pathlib.Path):
        if not p.exists(): return None
        try:
            s = p.stat()
            return {"size_bytes": s.st_size, "mtime": s.st_mtime}
        except Exception:
            return None

    info = {
        "index": _stat(idx),
        "docs": _stat(docs),
        "raw": _stat(raw),
    }

    # عدّ سريع لعدد الأسطر في docs.jsonl (اختياري)
    line_count = None
    if docs.exists():
        try:
            with open(docs, "r", encoding="utf-8", errors="ignore") as f:
                line_count = sum(1 for _ in f)
        except Exception:
            line_count = None

    # فحص قراءة FAISS (اختياري — يُتجاوز إذا لم تتوفر المكتبة)
    faiss_ok = None
    faiss_nt = None
    from nlp_core import _FAISS_OK, faiss
    if _FAISS_OK and idx.exists():
        try:
            index = faiss.read_index(idx.as_posix())
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

@app.get("/ultra-health")
def ultra_health():
    return {"ultra_model": settings.ULTRA_MODEL, "ultra_4bit": settings.ULTRA_4BIT, "trust_remote": settings.ULTRA_TRUST_REMOTE, "prompt_mode": settings.ULTRA_PROMPT_MODE}

# --------- أدوات استجابة موحدة ---------
def _response_ok(text: str, summary: str, keywords: str,
                 txt_path: Optional[str], summary_path: Optional[str],
                 segments: Optional[list] = None,
                 srt_path: Optional[str] = None, vtt_path: Optional[str] = None,
                 segments_path: Optional[str] = None) -> JSONResponse:
    base_url = settings.BASE_URL.rstrip("/")
    data = {
        "text": text or "",
        "summary": summary or "",
        "keywords": keywords or "",
        "request_id": _RID.get(),
        "txt_path": txt_path,
        "summary_path": summary_path,
        "summary_source": nlp_core.get_summary_source(),
        "segments": segments or [],
        "srt_path": srt_path,
        "vtt_path": vtt_path,
        "segments_path": segments_path,
    }
    if base_url and (txt_path or srt_path or vtt_path or summary_path):
        def _u(p): return f"{base_url}/download?path={quote(p)}" if p else None
        data["download_urls"] = {
            "txt": _u(txt_path),
            "srt": _u(srt_path),
            "vtt": _u(vtt_path),
            "summary": _u(summary_path),
        }
    return JSONResponse(data)

def _response_error(code: int, err: str, detail: Optional[str] = None) -> JSONResponse:
    payload = {
        "error": err, "detail": detail or "",
        "request_id": _RID.get(),
        "text": "", "summary": "", "keywords": "",
        "txt_path": None, "summary_path": None,
        "summary_source": nlp_core.get_summary_source(),
        "segments": [], "srt_path": None, "vtt_path": None, "segments_path": None,
        "download_urls": {"txt": None, "srt": None, "vtt": None, "summary": None},
    }
    return JSONResponse(payload, status_code=code)

# --- Job store ---
JOBS_DIR = settings.OUTPUTS_DIR / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)

# حالة داخلية خفيفة
_JOBS = {}  # job_id -> {"status": "queued|running|done|error", "result_path": str|None, "error": str|None}

def _job_file(job_id: str) -> pathlib.Path:
    return JOBS_DIR / f"{job_id}.json"

def _job_payload(status: str, result: dict | None = None, error: str | None = None) -> dict:
    return {"status": status, "result": result or {}, "error": error or ""}

async def _run_transcribe_job(job_id: str, tmp_path: pathlib.Path, kwargs: dict):
    core = _get_core()
    _JOBS[job_id] = {"status": "running", "result_path": None, "error": None}
    try:
        result = await asyncio.to_thread(core.process, str(tmp_path), **kwargs)
        if not isinstance(result, dict):
            raise RuntimeError("unexpected_result_type")
        payload = _job_payload("done", result, None)
        out = _job_file(job_id)
        out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        _JOBS[job_id]["status"] = "done"
        _JOBS[job_id]["result_path"] = out.as_posix()
    except Exception as e:
        payload = _job_payload("error", None, str(e))
        out = _job_file(job_id)
        out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        _JOBS[job_id]["status"] = "error"
        _JOBS[job_id]["error"] = str(e)
    finally:
        try:
            tmp_dir = tmp_path.parent
            tmp_path.unlink(missing_ok=True)
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

@app.post("/summarize")
@limiter.limit("12/minute")
async def summarize_after(
    text: Optional[str] = Form(None),
    path: Optional[str] = Form(None),
    summary_mode: str = Form("lite"),
    async_mode: bool = Form(False),   # <-- جديد
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    fake_file: Optional[UploadFile] = File(None),
    request: Request = None
):
    if settings.API_TOKEN and not secrets.compare_digest(x_api_key or "", settings.API_TOKEN):
        return _response_error(401, "unauthorized", "invalid api key")

    body = (text or "").strip()
    if (path or "").strip():
        try:
            p = pathlib.Path(path).expanduser().resolve()
            base = settings.OUTPUTS_DIR
            if base not in p.parents and base != p.parent:
                return _response_error(403, "forbidden_path", "outside outputs/")
            if not p.exists() or not p.is_file():
                return _response_error(404, "file_not_found", p.as_posix())
            body = p.read_text(encoding="utf-8", errors="ignore")
            out_base_path = p
        except Exception as e:
            return _response_error(500, "read_failed", str(e))
    else:
        out_base_path = settings.OUTPUTS_DIR / "manual_summary"

    if not body:
        return _response_error(400, "no_text", "nothing to summarize")

    if not async_mode:
        # المسار المتزامن كما كان
        s_text, kw_csv = nlp_core.summarize(body, mode=summary_mode)
        if not s_text.strip():
            nlp_core.set_summary_source("off")
            return JSONResponse({"summary": "", "keywords": "", "summary_path": None, "summary_source": "off"})
        try:
            sum_path = str(out_base_path.with_suffix(".summary.txt"))
            pathlib.Path(sum_path).write_text(
                s_text + (("\n\nالكلمات المفتاحية: " + (kw_csv or "")) if kw_csv else ""),
                encoding="utf-8"
            )
        except Exception:
            sum_path = None
        base = settings.BASE_URL.rstrip('/') or str(request.base_url).rstrip('/')
        summary_url = f"{base}/download?path={quote(sum_path)}" if (base and sum_path) else None
        return JSONResponse({
            "summary": s_text, "keywords": kw_csv or "", "summary_path": sum_path,
            "summary_source": nlp_core.get_summary_source(),
            "download_urls": {"summary": summary_url}
        })

    # مسار المهمة الخلفية
    job_id = str(uuid.uuid4())
    _JOBS[job_id] = {"status": "queued", "result_path": None, "error": None}
    asyncio.create_task(_run_summary_job(job_id, body, out_base_path, summary_mode))
    base = settings.BASE_URL.rstrip('/') or str(request.base_url).rstrip('/')
    return JSONResponse(
        {"job_id": job_id, "status": "queued", "poll_url": f"{base}/job/{job_id}", "result_url": f"{base}/job/{job_id}/download"},
        status_code=202
    )

@app.post("/ner")
async def ner_endpoint(
    text: Optional[str] = Form(None),
    path: Optional[str] = Form(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    if settings.API_TOKEN and not secrets.compare_digest(x_api_key or "", settings.API_TOKEN):
        return _response_error(401, "unauthorized", "invalid api key")
    body = (text or "").strip()
    if (path or "").strip():
        try:
            p = pathlib.Path(path).expanduser().resolve()
            base = settings.OUTPUTS_DIR
            if base not in p.parents and base != p.parent:
                return _response_error(403, "forbidden_path", "outside outputs/")
            if not p.exists() or not p.is_file():
                return _response_error(404, "file_not_found", p.as_posix())
            body = p.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            return _response_error(500, "read_failed", str(e))
    if not body:
        return _response_error(400, "no_text", "nothing to analyze")
    ents = nlp_core.extract_entities(body)
    return JSONResponse({"entities": ents})

# -------- أدوات مقاطع + SRT/VTT --------
def _parse_segments(text: str) -> list:
    segs = []
    for raw in (text or "").splitlines():
        line = raw.strip().lstrip("\u200f")  # إزالة RLM إن وُجد
        # النمط 1: [12.34→56.78] (المتكلم) النص
        m1 = re.match(
            r"^\[(\d+(?:\.\d+)?)\s*[\u2192\-\>]\s*(\d+(?:\.\d+)?)\]\s*\((.*?)\)\s*(.+)$",
            line
        )
        if m1:
            st = float(m1.group(1)); en = float(m1.group(2))
            who = m1.group(3).strip()
            txt = m1.group(4).strip()
            segs.append({"start": st, "end": en, "speaker": who, "text": txt})
            continue
        # النمط 2: (المتكلم) [12.34→56.78] النص  ← كما ينتجه asr_core
        m2 = re.match(
            r"^\((.*?)\)\s*\[(\d+(?:\.\d+)?)\s*[\u2192\-\>]\s*(\d+(?:\.\d+)?)\]\s*(.+)$",
            line
        )
        if m2:
            who = m2.group(1).strip()
            st = float(m2.group(2)); en = float(m2.group(3))
            txt = m2.group(4).strip()
            segs.append({"start": st, "end": en, "speaker": who, "text": txt})
    return segs

def _write_segments_json(segments: list, base_txt_path: str) -> Optional[str]:
    try:
        if not base_txt_path:
            return None
        p = pathlib.Path(base_txt_path).with_suffix(".segments.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(segments or [], f, ensure_ascii=False)
        return p.as_posix()
    except Exception:
        return None   

# ===============================================================================

@app.post("/transcribe")
@limiter.limit("6/minute")
async def transcribe(
    file: UploadFile = File(...),
    audio: UploadFile = File(None),
    async_mode: bool = Form(False),   # <--- جديد
    model_name: Optional[str] = Form(None),
    enhance: bool = Form(True),
    whisper_mode: str = Form("normal"),
    diarize: bool = Form(True),
    punctuate: bool = Form(False),
    auto_k: bool = Form(True),
    max_speakers: int = Form(2),
    enroll_threshold: float = Form(0.65),
    device_sel: str = Form("auto"),
    compute_sel: str = Form("auto"),
    summary_mode: str = Form("off"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    request: Request = None,
):
    if settings.API_TOKEN and not secrets.compare_digest(x_api_key or "", settings.API_TOKEN):
        return _response_error(401, "unauthorized", "invalid api key")
    core = _get_core()
    uf = file or audio
    if uf is None:
        return _response_error(400, "no_file", "use form field 'file' or 'audio'")
    nlp_core.set_summary_source("local")

    tmpdir = tempfile.mkdtemp(prefix="asr_")
    dst = pathlib.Path(tmpdir) / ((uf.filename) or "audio.wav")
    async with aiofiles.open(dst, "wb") as f:
        content = await uf.read()
        await f.write(content)

    # تحقق أساسي
    try:
        if dst.stat().st_size > settings.MAX_UPLOAD_MB * 1024 * 1024:
            try:
                shutil.rmtree(tmpdir)
            finally:
                return _response_error(413, "file_too_large", f"max={settings.MAX_UPLOAD_MB}MB")
    except Exception:
        pass
    if dst.suffix.lower() not in settings.ALLOWED_EXT:
        try:
            shutil.rmtree(tmpdir)
        finally:
            return _response_error(415, "unsupported_media_type", dst.suffix.lower())

    # مسار متزامن القديم
    if not async_mode:
        try:
            result = await asyncio.to_thread(
                core.process,
                str(dst),
                model_name = model_name or settings.WHISPER_MODEL,
                enhance = enhance,
                whisper_mode = whisper_mode,
                diarize = diarize,
                auto_k = auto_k,
                max_speakers = max_speakers,
                enroll_threshold = enroll_threshold,
                device_sel = device_sel,
                compute_sel = compute_sel,
                summary_mode = "off",
                punctuate = punctuate,
            )
            seg_path = result.get("segments_path") or _write_segments_json(result.get("segments") or [], result.get("txt_path"))
            return _response_ok(result.get("text",""), result.get("summary","") or "", result.get("keywords","") or "",
                                result.get("txt_path"), result.get("summary_path"),
                                result.get("segments") or [], result.get("srt_path"), result.get("vtt_path"), seg_path)
        finally:
            try: shutil.rmtree(tmpdir)
            except Exception: pass

    # مسار المهام الخلفية
    # جهّز kwargs للـ core.process
    kwargs = dict(
        model_name = model_name or settings.WHISPER_MODEL,
        enhance = enhance,
        whisper_mode = whisper_mode,
        diarize = diarize,
        auto_k = auto_k,
        max_speakers = max_speakers,
        enroll_threshold = enroll_threshold,
        device_sel = device_sel,
        compute_sel = compute_sel,
        summary_mode = "off",
        punctuate = punctuate,
    )
    job_id = str(uuid.uuid4())
    _JOBS[job_id] = {"status": "queued", "result_path": None, "error": None}
    asyncio.create_task(_run_transcribe_job(job_id, dst, kwargs))
    base = settings.BASE_URL.rstrip('/') or str(request.base_url).rstrip('/')
    return JSONResponse(
        {"job_id": job_id, "status": "queued", "poll_url": f"{base}/job/{job_id}", "result_url": f"{base}/job/{job_id}/download"},
        status_code=202
    )

@app.post("/transcribe-batch")
async def transcribe_batch(
    files: List[UploadFile] = File(...),
    model_name: Optional[str] = Form(None),
    enhance: bool = Form(True),
    whisper_mode: str = Form("normal"),
    diarize: bool = Form(True),
    punctuate: bool = Form(False),
    auto_k: bool = Form(True),
    max_speakers: int = Form(2),
    enroll_threshold: float = Form(0.65),
    device_sel: str = Form("auto"),
    compute_sel: str = Form("auto"),
    summary_mode: str = Form("off"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    request: Request = None,
):
    if settings.API_TOKEN and not secrets.compare_digest(x_api_key or "", settings.API_TOKEN):
        return _response_error(401, "unauthorized", "invalid api key")
    core = _get_core()
    nlp_core.set_summary_source("local")

    tmpdir = tempfile.mkdtemp(prefix="asr_batch_")
    try:
        saved: List[str] = []
        for uf in files:
            dst = pathlib.Path(tmpdir) / (uf.filename or f"audio_{len(saved)}.wav")
            async with aiofiles.open(dst, "wb") as f:
                content = await uf.read()
                await f.write(content)
            # تحقق سريع لكل ملف
            if dst.suffix.lower() not in settings.ALLOWED_EXT:
                dst.unlink(missing_ok=True)
                return _response_error(415, "unsupported_media_type", dst.suffix.lower())
            if dst.stat().st_size > settings.MAX_UPLOAD_MB * 1024 * 1024:
                dst.unlink(missing_ok=True)
                return _response_error(413, "file_too_large", f"max={settings.MAX_UPLOAD_MB}MB")
            saved.append(str(dst))

        try:
            result = await asyncio.to_thread(
                core.process_many,
                saved,
                model_name = model_name or settings.WHISPER_MODEL,
                enhance = enhance,
                whisper_mode = whisper_mode,
                diarize = diarize,
                auto_k = auto_k,
                max_speakers = max_speakers,
                enroll_threshold = enroll_threshold,
                device_sel = device_sel,
                compute_sel = compute_sel,
                summary_mode = "off",
                punctuate = punctuate,
            )

            if not isinstance(result, dict):
                return _response_error(500, "unexpected_result_type")

            merged_text = result.get("text","")
            merged_path = result.get("txt_path")
            merged_sum = result.get("summary","") or ""
            keywords = result.get("keywords","") or ""
            merged_sum_path = result.get("summary_path")

            if summary_mode and summary_mode.lower() != "off":
                if not (merged_sum or "").strip():
                    try:
                        s_text, kw_csv = nlp_core.summarize(merged_text, mode=summary_mode)
                    except HTTPException as he:
                        raise he
                    merged_sum, keywords = s_text, kw_csv
                try:
                    if (merged_sum or "").strip():
                        sum_p = pathlib.Path(merged_path).with_suffix(".summary.txt")
                        sum_p.write_text(
                            merged_sum + (("\n\nالكلمات المفتاحية: " + (keywords or "")) if keywords else ""),
                            encoding="utf-8"
                        )
                        merged_sum_path = str(sum_p)
                except Exception as e:
                    print(f"[WRITE_SUMMARY_BATCH] {e}")
            else:
                nlp_core.set_summary_source("off")

            # استخدم مخرجات asr_core.process_many مباشرة
            segs      = result.get("segments") or _parse_segments(merged_text)
            srt_path  = result.get("srt_path")
            vtt_path  = result.get("vtt_path")
            seg_path  = result.get("segments_path") or _write_segments_json(segs, merged_path)
            return _response_ok(merged_text, merged_sum, keywords, merged_path, merged_sum_path, segs, srt_path, vtt_path, seg_path)

        except HTTPException as he:
            raise he
        except Exception:
            return _response_error(500, "processing_failed", traceback.format_exc())

    finally:
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass

@app.get("/download")
def download_txt(path: str = Query(..., description="Absolute or outputs-relative path to txt file"),
                 x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    if settings.API_TOKEN and not secrets.compare_digest(x_api_key or "", settings.API_TOKEN):
        return _response_error(401, "unauthorized", "invalid api key")
    try:
        base = settings.OUTPUTS_DIR
        p = pathlib.Path(path).expanduser().resolve()
        if base not in p.parents and base != p.parent:
            return _response_error(403, "forbidden_path", "outside outputs/")
        if not p.exists() or not p.is_file():
            return _response_error(404, "file_not_found", p.as_posix())
        # حظر الامتدادات غير المسموح تنزيلها
        if p.suffix.lower() not in settings.DOWNLOAD_ALLOW:
            return _response_error(403, "forbidden_extension", p.suffix.lower())
        return FileResponse(p.as_posix(), media_type="text/plain", filename=p.name)
    except Exception as e:
        return _response_error(500, "download_failed", str(e))
    
@app.get("/export.srt")
def export_srt(path: str = Query(..., description="Absolute or outputs-relative path to txt transcript"),
               x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    if settings.API_TOKEN and not secrets.compare_digest(x_api_key or "", settings.API_TOKEN):
        return _response_error(401, "unauthorized", "invalid api key")
    try:
        base = settings.OUTPUTS_DIR
        core = _get_core()
        p = pathlib.Path(path).expanduser().resolve()
        if base not in p.parents and base != p.parent:
            return _response_error(403, "forbidden_path", "outside outputs/")
        if not p.exists() or not p.is_file():
            return _response_error(404, "file_not_found", p.as_posix())
        # إذا كان ملف SRT جاهزًا بجانب النص فاستعمله مباشرة
        srt_ready = p.with_suffix(".srt")
        if srt_ready.exists():
            srt_path = srt_ready.as_posix()
        else:
            txt = p.read_text(encoding="utf-8", errors="ignore")
            segs = _parse_segments(txt)
            srt_path = core.segments_to_srt(segs, p.as_posix())
        if not srt_path:
            return _response_error(500, "srt_failed")
        return FileResponse(srt_path, media_type="application/x-subrip", filename=pathlib.Path(srt_path).name)
    except Exception as e:
        return _response_error(500, "srt_failed", str(e))

@app.get("/export.vtt")
def export_vtt(path: str = Query(..., description="Absolute or outputs-relative path to txt transcript"),
               x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    if settings.API_TOKEN and not secrets.compare_digest(x_api_key or "", settings.API_TOKEN):
        return _response_error(401, "unauthorized", "invalid api key")
    try:
        base = settings.OUTPUTS_DIR
        core = _get_core()
        p = pathlib.Path(path).expanduser().resolve()
        if base not in p.parents and base != p.parent:
            return _response_error(403, "forbidden_path", "outside outputs/")
        if not p.exists() or not p.is_file():
            return _response_error(404, "file_not_found", p.as_posix())
        # إذا كان ملف VTT جاهزًا بجانب النص فاستعمله مباشرة
        vtt_ready = p.with_suffix(".vtt")
        if vtt_ready.exists():
            vtt_path = vtt_ready.as_posix()
        else:
            txt = p.read_text(encoding="utf-8", errors="ignore")
            segs = _parse_segments(txt)
            vtt_path = core.segments_to_vtt(segs, p.as_posix())
        if not vtt_path:
            return _response_error(500, "vtt_failed")
        return FileResponse(vtt_path, media_type="text/vtt", filename=pathlib.Path(vtt_path).name)
    except Exception as e:
        return _response_error(500, "vtt_failed", str(e))    

@app.get("/segments")
def segments_json(path: str = Query(..., description="Absolute or outputs-relative path to txt transcript"),
                  x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
                  request: Request = None):
    if settings.API_TOKEN and not secrets.compare_digest(x_api_key or "", settings.API_TOKEN):
        return _response_error(401, "unauthorized", "invalid api key")
    base = settings.OUTPUTS_DIR
    p = pathlib.Path(path).expanduser().resolve()
    if base not in p.parents and base != p.parent:
        return _response_error(403, "forbidden_path", "outside outputs/")
    if not p.exists() or not p.is_file():
        return _response_error(404, "file_not_found", p.as_posix())
    txt = p.read_text(encoding="utf-8", errors="ignore")
    return JSONResponse(_parse_segments(txt))

@app.get("/segments/download")
def segments_download(path: str = Query(..., description="Absolute or outputs-relative path to txt transcript"),
                      x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
                      request: Request = None):
    if settings.API_TOKEN and not secrets.compare_digest(x_api_key or "", settings.API_TOKEN):
        return _response_error(401, "unauthorized", "invalid api key")
    base = settings.OUTPUTS_DIR
    p = pathlib.Path(path).expanduser().resolve()
    if base not in p.parents and base != p.parent:
        return _response_error(403, "forbidden_path", "outside outputs/")
    if not p.exists() or not p.is_file():
        return _response_error(404, "file_not_found", p.as_posix())
    txt = p.read_text(encoding="utf-8", errors="ignore")
    segs = _parse_segments(txt)
    fname = p.with_suffix(".segments.json").name
    return Response(
        content=json.dumps(segs, ensure_ascii=False, indent=2),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'}
    )

@app.get("/job/{job_id}")
def job_status(job_id: str):
    meta = _JOBS.get(job_id, None)
    file = _job_file(job_id)
    if file.exists():
        data = json.loads(file.read_text(encoding="utf-8"))
        return data  # يحتوي status و result أو error
    if meta is None:
        return _response_error(404, "job_not_found")
    return JSONResponse({"status": meta["status"], "result": {}, "error": meta.get("error") or ""})

@app.get("/job/{job_id}/download")
def job_download(job_id: str):
    p = _job_file(job_id)
    if not p.exists():
        return _response_error(404, "job_not_ready")
    return FileResponse(p.as_posix(), media_type="application/json", filename=p.name)

# --- Summary job ---
async def _run_summary_job(job_id: str, body: str, out_base_path: pathlib.Path, summary_mode: str):
    try:
        s_text, kw_csv = nlp_core.summarize(body, mode=summary_mode)
        if not s_text.strip():
            payload = _job_payload("done", {
                "summary": "", "keywords": "", "summary_path": None, "summary_source": "off"
            })
        else:
            try:
                sum_path = str(out_base_path.with_suffix(".summary.txt"))
                pathlib.Path(sum_path).write_text(
                    s_text + (("\n\nالكلمات المفتاحية: " + (kw_csv or "")) if kw_csv else ""),
                    encoding="utf-8"
                )
            except Exception:
                sum_path = None
            payload = _job_payload("done", {
                "summary": s_text, "keywords": kw_csv or "", "summary_path": sum_path,
                "summary_source": nlp_core.get_summary_source()
            })
        out = _job_file(job_id)
        out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        _JOBS[job_id] = {"status": "done", "result_path": out.as_posix(), "error": None}
    except Exception as e:
        out = _job_file(job_id)
        out.write_text(json.dumps(_job_payload("error", None, str(e)), ensure_ascii=False), encoding="utf-8")
        _JOBS[job_id] = {"status": "error", "result_path": None, "error": str(e)}

@app.get("/models")
def get_available_models():
    try:
        core = _get_core()
        return {
            "models": getattr(core, "MODEL_CHOICES", ["light", "heavy"]),
            "default": getattr(core, "DEFAULT_MODEL", settings.WHISPER_MODEL),
        }
    except Exception:
        return {"models": ["light", "heavy"], "default": settings.WHISPER_MODEL}

@app.post("/enroll-speaker")
async def enroll_speaker(
    name: str = Form(...),
    files: List[UploadFile] = File(...),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    if settings.API_TOKEN and not secrets.compare_digest(x_api_key or "", settings.API_TOKEN):
       return _response_error(401, "unauthorized", "invalid api key")
    core = _get_core()
    tmpdir = tempfile.mkdtemp(prefix="enroll_")
    try:
        saved_files: List[str] = []
        for uf in files:
            dst = pathlib.Path(tmpdir) / (uf.filename or f"voice_{len(saved_files)}.wav")
            async with aiofiles.open(dst, "wb") as f:
                content = await uf.read()
                await f.write(content)
            try:
                if dst.stat().st_size > settings.MAX_UPLOAD_MB * 1024 * 1024:
                    return _response_error(413, "file_too_large", f"max={settings.MAX_UPLOAD_MB}MB")
            except Exception:
                pass
            if dst.suffix.lower() not in settings.ALLOWED_EXT:
                return _response_error(415, "unsupported_media_type", dst.suffix.lower())
            saved_files.append(str(dst))
        success, message = core.enroll_voice(name, saved_files)
        return JSONResponse({"success": bool(success), "message": message or ""})
    except Exception as e:
        return _response_error(500, "enrollment_failed", str(e))
    finally:
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass

@app.get("/enrolled-speakers")
def get_enrolled_speakers(x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    if settings.API_TOKEN and not secrets.compare_digest(x_api_key or "", settings.API_TOKEN):
        return _response_error(401, "unauthorized", "invalid api key")
    try:
        core = _get_core()
        speakers = core.load_enrolled()
        return {"speakers": speakers}
    except Exception as e:
        return _response_error(500, "failed_to_load_speakers", str(e))