# api.py - نسخة مستقرة مُحسّنة
import os, tempfile, shutil, pathlib, re, collections, subprocess, json, traceback
from typing import List, Tuple, Optional, Set
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, Header, Request
import contextvars
import warnings
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, FileResponse, Response, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from urllib.parse import quote
import logging

import sys, asyncio
if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

try:
    from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, AutoModelForCausalLM, pipeline  # type: ignore
    try:
        # اختياري: للتكميم 4-بت إذا توفّر
        from transformers import BitsAndBytesConfig  # type: ignore
    except Exception:
        BitsAndBytesConfig = None  # type: ignore
    _TF_AVAILABLE = True
except Exception:
    _TF_AVAILABLE = False

warnings.filterwarnings("ignore", message="You are using the default legacy behaviour of the <class 'transformers.models.t5.tokenization_t5.T5Tokenizer'>")
warnings.filterwarnings("ignore", message="The sentencepiece tokenizer that you are converting to a fast tokenizer uses the byte fallback option.*")
logger = logging.getLogger("asr_api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = FastAPI(title="Arabic ASR API", version="0.1.2")
_RID: contextvars.ContextVar[str] = contextvars.ContextVar("rid", default="")

# جذر البيانات الموحد
DATA_DIR = pathlib.Path(os.getenv("ASR_DATA_DIR", "data")).resolve()
OUTPUTS_DIR = (DATA_DIR / "outputs").resolve()
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

# ===================== تعديل: تفضيل النماذج المحلية =====================
LOCAL_MODELS = (DATA_DIR / "models").resolve()
E5_BASE_DIR  = (LOCAL_MODELS / "multilingual-e5-base")
SUM_MT5_DIR  = (LOCAL_MODELS / "summarizers" / "mT5_XLSum")

# إذا وُجد المسار المحلي خذه، وإلا استخدم الاسم الافتراضي
def _prefer_local(path: pathlib.Path, fallback: str):
    return path.as_posix() if path.exists() else fallback

# RAG embeddings model
_rag_mname = os.getenv("RAG_EMB_MODEL",
    _prefer_local(E5_BASE_DIR, "intfloat/multilingual-e5-base"))

# Summarizer model
_TF_MODEL = os.getenv("SUMMARIZER_MODEL",
    _prefer_local(SUM_MT5_DIR, "csebuetnlp/mT5_multilingual_XLSum"))

# حدود تلخيص آمنة للذاكرة
SUM_MAX_INPUT_TOKENS = max(256, int(os.getenv("SUM_MAX_INPUT_TOKENS", "800")))  # إدخال كل جزء
SUM_MAX_PARTS = max(1, int(os.getenv("SUM_MAX_PARTS", "8")))  # حد أقصى لعدد الأجزاء

os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", (LOCAL_MODELS).as_posix())
# Lifespan replaces deprecated on_event("startup")
@asynccontextmanager
async def _lifespan(_: FastAPI):
    if os.getenv("ASR_WARMUP", "0") in ("1", "true", "True"):
        try:
            _ = _get_core()  # preload models, ffmpeg check happens later in /health
        except Exception as e:
            print(f"[warmup] skipped: {e}")
    yield

app.router.lifespan_context = _lifespan
if pathlib.Path("static").exists():
    app.mount("/static", StaticFiles(directory="static", html=False), name="static")

# api.py
allow = os.getenv("ASR_ALLOWED_ORIGINS", "").split(",") if os.getenv("ASR_ALLOWED_ORIGINS") else []
app.add_middleware(CORSMiddleware, allow_origins=allow or ["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=1024)

# حدّ حجم الطلب قبل الكتابة على القرص
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
            if cl and float(cl) > MAX_UPLOAD_MB * 1024 * 1024:
                resp = _response_error(413, "file_too_large", f"max={MAX_UPLOAD_MB}MB")
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

# افتراضيات
_DEFAULT_MODEL = os.getenv("WHISPER_MODEL", "light")
_HAS_CUDA = False

API_TOKEN = os.getenv("API_TOKEN", "").strip()
MAX_UPLOAD_MB = float(os.getenv("MAX_UPLOAD_MB", "50"))
ALLOWED_EXT = {".wav",".mp3",".m4a",".mp4",".ogg",".flac",".webm",".aac",".3gp",".opus"}
_DOWNLOAD_ALLOW = {".txt", ".srt", ".vtt", ".json"}
# إعدادات المُلخِّصات
_TF_FALLBACK = True
_TF_DEVICE = int(os.getenv("HF_DEVICE_ID", "-1"))  # CPU=-1
# ULTRA = Jais-13B-Chat عبر Transformers (يدعم العربية بقوة)
# يمكن تمرير مسار محلي أو معرف HF عبر ULTRA_MODEL
_ULTRA_MODEL   = os.getenv("ULTRA_MODEL", "inceptionai/jais-13b-chat")
_ULTRA_4BIT    = os.getenv("ULTRA_4BIT", "1").lower() in ("1","true","yes")
_HF_TOKEN      = os.getenv("HF_TOKEN", "").strip() or None
_TRUST_REMOTE  = True  # مطلوب لـ Jais
_ULTRA_PROMPT_MODE = os.getenv("ULTRA_PROMPT_MODE", "auto").lower()

# ==================== ArabicText-Large RAG ====================
import json, numpy as np
try:
    import faiss  # اختياري
    _FAISS_OK = True
except Exception:
    faiss = None
    _FAISS_OK = False
try:
    from sentence_transformers import SentenceTransformer  # اختياري
    _ST_OK = True
except Exception:
    SentenceTransformer = None
    _ST_OK = False

_RAG_DIR = (DATA_DIR / "rag" / "arabictext_large").resolve()
_RAG_INDEX = _RAG_DIR / "index.faiss"
_RAG_DOCS = _RAG_DIR / "docs.jsonl"
_rag_index = None
_rag_model = None
_rag_texts = []
_rag_dim   = None

def _rag_load():
    """تحميل الفهرس والنصوص والـembeddings"""
    global _rag_index, _rag_model, _rag_texts, _rag_dim
    if _rag_index is not None:
        return
    # عطّل إذا المكتبات أو الملفات غير متوفرة
    if not (_FAISS_OK and _ST_OK):
        print("[RAG] disabled (faiss or sentence-transformers missing).")
        return
    if not _RAG_INDEX.exists() or not _RAG_DOCS.exists():
        print("[RAG] no ArabicText-Large index found.")
        return
    print("[RAG] loading FAISS + docs ...")
    _rag_index = faiss.read_index(_RAG_INDEX.as_posix())
    with open(_RAG_DOCS, "r", encoding="utf-8") as f:
        _rag_texts = [json.loads(line).get("text", "") for line in f]
    _rag_model = SentenceTransformer(_rag_mname)
    try:
        print(f"[RAG] model={_rag_mname} loaded")
    except Exception: pass
    _rag_dim = getattr(_rag_model, "get_sentence_embedding_dimension", lambda: None)()
    try:
        if _rag_dim and _rag_index.d != int(_rag_dim):
            print(f"[RAG] dim mismatch: index.d={_rag_index.d} vs model.d={_rag_dim} → disabling RAG")
            _rag_index = None  # عطّل RAG لمنع الأخطاء
    except Exception as e:
        print(f"[RAG] dim check failed: {e}")

def _rag_retrieve(query: str, k: int = 6) -> str:
    """يسترجع مقاطع مشابهة من ArabicText-Large"""
    if not query.strip():
        return ""
    _rag_load()
    if _rag_index is None:
        return ""
    qv = _rag_model.encode([f"query: {query}"], normalize_embeddings=True)
    qv = np.asarray(qv, dtype="float32")
    try:
        k = max(1, min(k, getattr(_rag_index, "ntotal", k)))
        D, I = _rag_index.search(qv, k)
    except Exception as e:
        print(f"[RAG] search failed: {e}")
        return ""
    ctx = "\n\n".join(_rag_texts[i] for i in I[0] if i < len(_rag_texts))
    return ctx.strip()

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
    if API_TOKEN and (x_api_key or "") != API_TOKEN:
        return _response_error(401, "unauthorized", "invalid api key")
    core = _get_core()
    ok, msg = core.delete_speaker(name)
    return {"success": bool(ok), "message": msg}

@app.get("/speaker-files")
def speaker_files(name: str = Query(...), x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    if API_TOKEN and (x_api_key or "") != API_TOKEN:
        return _response_error(401, "unauthorized", "invalid api key")
    core = _get_core()
    return {"files": core.get_speaker_files(name)}

@app.get("/health")
def health():
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
            "model_default": getattr(core, "DEFAULT_MODEL", _DEFAULT_MODEL),
            "cuda": getattr(core, "_HAS_CUDA", _HAS_CUDA),
            "ollama_enabled": False,
            "ffmpeg": ffmpeg_ok,
            "gpu_name": gpu_name,
            "data_dir": str(OUTPUTS_DIR.parent),
            "max_upload_mb": MAX_UPLOAD_MB,
            "allowed_ext": sorted(ALLOWED_EXT),
        }
    except Exception:
        gpu_name = ""
        try:
            import torch
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
        except Exception:
            pass
        return {
            "status": "degraded",
            "model_default": _DEFAULT_MODEL,
            "cuda": _HAS_CUDA,
            "ollama_enabled": False,
            "ffmpeg": False,
            "gpu_name": gpu_name,
            "data_dir": str(OUTPUTS_DIR.parent),
            "max_upload_mb": MAX_UPLOAD_MB,
            "allowed_ext": sorted(ALLOWED_EXT),
        }
    
# ---- RAG health (اختياري) ----
@app.get("/rag-health")
def rag_health():
    rag_dir = (DATA_DIR / "rag" / "arabictext_large").resolve()
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

# ======================= أدوات العربية ========================
_AR_STOP = set("""
في على الى إلى مع عن من ما هذا هذه ذلك تلك هناك هنا ثم حيث لقد قد كان كانت يكون كانوا كنت إن أن لكن لأن لو إذا إذ كما ربما حتى بين لدى لديهم لدي إليها فيها منه منها فيه بها بهان بنا لكم لنا فقط جدا جدًا حقا حقيقة أيضًا أيضاً قبل بعد خلال أثناء ضد عبر نحو فوق تحت بين إلا علًى إلًى بأن وإنّ أنّ لا لم لن ليس بدون غير كافة جميع بعض أي أحد
نعم مثل ايضا ايضاً جداً جدا حقاً حقا
""".split())

def _normalize_ar(s: str) -> str:
    s = s.replace("\u0640", "")
    s = re.sub("[\u0617-\u061A\u064B-\u0652]", "", s)
    s = re.sub("[\u0622\u0623\u0625]", "\u0627", s)
    s = s.replace("ى", "ي").replace("ئ", "ي").replace("ؤ", "و").replace("ة", "ه")
    return s

def _tokenize_ar(s: str) -> list:
    s = _normalize_ar(s)
    toks = re.findall(r"[اأإآابتثجحخدذرزسشصضطظعغفقكلمنهوية]+", s)
    return [t for t in toks if t not in _AR_STOP and len(t) > 1]

def _keywords_ar(text: str, k: int = 8) -> list:
    cnt = collections.Counter(_tokenize_ar(text))
    return [w for w, _ in cnt.most_common(k)]

def _clean_for_summary(text: str) -> str:
    text = re.sub(r"(?m)^\s*المدة\s*:\s*.*?(?:\|\s*اللغة\s*:\s*.*)?(?:\|\s*ثقة\s*:\s*.*)?\s*$", " ", text)
    text = re.sub(r"(?m)^\s*[^:\n]{0,20}\s*\|\s*اللغة\s*:.*$", " ", text)
    text = re.sub(r"\[\d+(?:\.\d+)?[^\]]*\]", " ", text)
    text = re.sub(r"\(متكلم\s*\d+\)", " ", text)
    text = re.sub(r"###\s*ملف:.*", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

# ------------------- Summarizers -------------------
_ABST_PIPE = None
def _load_abstractive_pipe():
    """mT5 للوضع lite فقط."""
    global _ABST_PIPE
    if _ABST_PIPE is not None or not (_TF_AVAILABLE and _TF_FALLBACK):
        return _ABST_PIPE
    try:
        tok = AutoTokenizer.from_pretrained(_TF_MODEL)
        mdl = AutoModelForSeq2SeqLM.from_pretrained(_TF_MODEL)
        try:
            tok.model_max_length = min(getattr(tok, "model_max_length", 1_000_000), 1024)
        except Exception:
            pass
        _ABST_PIPE = pipeline("summarization", model=mdl, tokenizer=tok, device=_TF_DEVICE)
        return _ABST_PIPE
    except Exception as e:
        print(f"[TF] mT5 load failed: {e}")
        return None
    
def _chunks_by_tokens(text: str, tok, max_tokens: int) -> list:
    """
    قصّ على مرحلتين لمنع تحذير 17261>1024 وتسريع العمل:
    1) تقطيع خشن بالحروف إلى كتل ~6000 حرف.
    2) لكل كتلة: ترميز ثم تقطيع إلى أجزاء <= max_tokens.
    """
    parts: list[str] = []
    rough_step = 6000
    blocks = [text[i:i+rough_step] for i in range(0, len(text), rough_step)] or [text]
    for blk in blocks:
        try:
            ids = tok.encode(blk, add_special_tokens=False)
            for i in range(0, len(ids), max_tokens):
                seg = tok.decode(ids[i:i+max_tokens], skip_special_tokens=True).strip()
                if seg:
                    parts.append(seg)
        except Exception:
            parts.append(blk.strip())
        if len(parts) >= SUM_MAX_PARTS:
            break
    return parts[:SUM_MAX_PARTS] or [text]

def _summarize_abstractive(text: str, target_len: int = 220) -> str:
    p = _load_abstractive_pipe()
    if p is None:
        return ""
    clean = _clean_for_summary(text)
    try:
        tok = p.tokenizer
        parts = _chunks_by_tokens(clean, tok, max_tokens=min(SUM_MAX_INPUT_TOKENS, getattr(tok, "model_max_length", 1024)))
        summaries = []
        for seg in parts:
            out = p(
                seg,
                max_length=min(220, target_len),
                min_length=60,
                do_sample=False,
                truncation=True,
                num_beams=2,
            )
            summaries.append((out[0].get("summary_text") or "").strip())
        # دمج ثم ضغط ملخص الملخص
        merged = " ".join(s for s in summaries if s)
        if not merged:
            return ""
        if len(parts) > 1:
            out2 = p(merged, max_length=min(240, target_len+40), min_length=80, do_sample=False, truncation=True, num_beams=2)
            summ = (out2[0].get("summary_text") or "").strip()
        else:
            summ = merged.strip()
        if summ:
            globals()["_SUMMARY_SOURCE"] = f"transformers:{_TF_MODEL}"
        return summ
    except Exception as e:
        print(f"[TF] mT5 summarize failed: {e}")
        return ""

_ULTRA_PIPE = None
def _load_ultra_pipe():
    """تحميل Jais-13B-Chat للتوليد (وضع ultra)."""
    global _ULTRA_PIPE
    if _ULTRA_PIPE is not None:
        return _ULTRA_PIPE
    if not _TF_AVAILABLE:
        return None
    try:
        # يحمّل محليًا إن وُجد أو من HF. وجوب trust_remote_code لـ Jais.
        tok = AutoTokenizer.from_pretrained(
            _ULTRA_MODEL,
            token=_HF_TOKEN,
            trust_remote_code=_TRUST_REMOTE
        )
        if _ULTRA_4BIT and BitsAndBytesConfig is not None:
            bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype="float16")  # type: ignore
            mdl = AutoModelForCausalLM.from_pretrained(
                _ULTRA_MODEL,
                token=_HF_TOKEN,
                trust_remote_code=_TRUST_REMOTE,
                device_map="auto",
                quantization_config=bnb
            )
        else:
            mdl = AutoModelForCausalLM.from_pretrained(
                _ULTRA_MODEL,
                token=_HF_TOKEN,
                trust_remote_code=_TRUST_REMOTE,
                device_map="auto",
                torch_dtype="auto"
            )
        # ملاحظة: عند تمرير model محمّل بـ device_map، لا نحتاج لتحديد device في pipeline
        _ULTRA_PIPE = pipeline("text-generation", model=mdl, tokenizer=tok)
        return _ULTRA_PIPE
    except Exception as e:
        print(f"[TF] ULTRA load failed: {e}")
        return None

def _summarize_ultra(text: str, target_len: int = 220) -> str:
    p = _load_ultra_pipe()
    if p is None:
        return ""
    clean = _clean_for_summary(text)
    # تحديد نمط البرومبت
    mode = _ULTRA_PROMPT_MODE
    if mode == "auto":
        name = (_ULTRA_MODEL or "").lower()
        mode = "chat" if ("-chat" in name) else "plain"
    if mode == "chat":
        prompt = (
            "### Instruction: لخّص النص التالي بالعربية الفصحى في 4-6 جمل قصيرة وواضحة،"
            " امنع الحشو وكرر الأفكار الأساسية فقط.\n"
            f"### Input: [|Human|] {clean}\n"
            "### Response: [|AI|]"
        )
    else:
        prompt = (
            "لخّص النص التالي بالعربية الفصحى في 4-6 جمل قصيرة وواضحة،"
            " بدون حشو وبتركيز على الأفكار الأساسية:\n\n"
            f"{clean}\n\nالملخص:"
        )
    try:
        out = p(
            prompt,
            max_new_tokens=min(300, target_len+120),
            do_sample=False
        )[0]["generated_text"]
        if mode == "chat":
            spl = out.split("### Response: [|AI|]")
            summ = (spl[-1] if len(spl) > 1 else out).strip()
        else:
            summ = out.split("الملخص:")[-1].strip() if "الملخص:" in out else out.strip()
        if summ:
            globals()["_SUMMARY_SOURCE"] = f"transformers:{_ULTRA_MODEL}"
        return summ
    except Exception as e:
        print(f"[TF] ULTRA summarize failed: {e}")
        return ""

def _summarize(text: str, mode: str = "lite") -> Tuple[str, str]:
    if not text or not mode:
        globals()["_SUMMARY_SOURCE"] = "off"
        return ("", "")
    clean = _clean_for_summary(text)
    m = mode.lower()

    # off
    if m == "off":
        globals()["_SUMMARY_SOURCE"] = "off"
        return ("", "")
    
    # lite = mT5 (XLSum)
    if m == "lite":
        print("[SUM] lite -> mT5 (XLSum)")
        s_abs = _summarize_abstractive(clean, target_len=220)
        if s_abs:
            globals()["_SUMMARY_SOURCE"] = f"transformers:{_TF_MODEL}"
        return (s_abs or "", ", ".join(_keywords_ar(clean, k=10)) if s_abs else "")

    # ultra = ALLaM-13B-Instruct + RAG اختياري
    if m == "ultra":
        print("[SUM] ultra -> Jais-13B-Chat")
        ctx = _rag_retrieve(clean, k=3)
        prompt = f"السياق المسترجع:\n{ctx}\n\nالنص:\n{clean}" if ctx else clean
        s_ultra = _summarize_ultra(prompt, target_len=220)
        return (s_ultra or "", ", ".join(_keywords_ar(clean, k=10)) if s_ultra else "")

    # أي قيمة أخرى غير مدعومة
    raise HTTPException(status_code=400, detail=f"unsupported summary_mode: {mode}")

@app.get("/ultra-health")
def ultra_health():
    return {"ultra_model": _ULTRA_MODEL, "ultra_4bit": _ULTRA_4BIT, "trust_remote": _TRUST_REMOTE, "prompt_mode": _ULTRA_PROMPT_MODE}

def _renumber_speakers(text: str) -> str:
    mapping, next_id = {}, 1
    def repl(m):
        nonlocal next_id
        old = m.group(1)
        if old not in mapping:
            mapping[old] = str(next_id); next_id += 1
        return f"(متكلم {mapping[old]})"
    return re.sub(r"\(متكلم\s+(\d+)\)", repl, text)

# --------- أدوات استجابة موحدة ---------
def _response_ok(text: str, summary: str, keywords: str,
                 txt_path: Optional[str], summary_path: Optional[str],
                 segments: Optional[list] = None,
                 srt_path: Optional[str] = None, vtt_path: Optional[str] = None,
                 segments_path: Optional[str] = None) -> JSONResponse:
    base_url = os.getenv("BASE_URL", "").rstrip("/")
    data = {
        "text": text or "",
        "summary": summary or "",
        "keywords": keywords or "",
        "request_id": _RID.get(),
        "txt_path": txt_path,
        "summary_path": summary_path,
        "summary_source": globals().get("_SUMMARY_SOURCE", "local"),
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
        "summary_source": globals().get("_SUMMARY_SOURCE","local"),
        "segments": [], "srt_path": None, "vtt_path": None, "segments_path": None,
        "download_urls": {"txt": None, "srt": None, "vtt": None, "summary": None},
    }
    return JSONResponse(payload, status_code=code)

@app.post("/summarize")
async def summarize_after(
    text: Optional[str] = Form(None),
    path: Optional[str] = Form(None),
    summary_mode: str = Form("lite"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    # auth
    if API_TOKEN and (x_api_key or "") != API_TOKEN:
        return _response_error(401, "unauthorized", "invalid api key")
    # احضر النص: من path (موثّق داخل outputs/) أو من text
    body = (text or "").strip()
    if (path or "").strip():
        try:
            p = pathlib.Path(path).expanduser().resolve()
            base = OUTPUTS_DIR
            if base not in p.parents and base != p.parent:
                return _response_error(403, "forbidden_path", "outside outputs/")
            if not p.exists() or not p.is_file():
                return _response_error(404, "file_not_found", p.as_posix())
            body = p.read_text(encoding="utf-8", errors="ignore")
            out_base = p
        except Exception as e:
            return _response_error(500, "read_failed", str(e))
    else:
        out_base = OUTPUTS_DIR / "manual_summary"

    if not body:
        return _response_error(400, "no_text", "nothing to summarize")

    # لخّص
    s_text, kw_csv = _summarize(body, mode=summary_mode)
    if not s_text.strip():
        globals()["_SUMMARY_SOURCE"] = "off"
        return JSONResponse({
            "summary": "",
            "keywords": "",
            "summary_path": None,
            "summary_source": "off",
        })

    # اكتب ملف الملخص بجانب التفريغ إن وُجد
    try:
        sum_path = str(out_base.with_suffix(".summary.txt"))
        pathlib.Path(sum_path).write_text(
            s_text + (("\n\nالكلمات المفتاحية: " + (kw_csv or "")) if kw_csv else ""),
            encoding="utf-8"
        )
    except Exception:
        sum_path = None

    return JSONResponse({
        "summary": s_text,
        "keywords": kw_csv or "",
        "summary_path": sum_path,
        "summary_source": globals().get("_SUMMARY_SOURCE", "local"),
        "download_urls": {
        "summary": (f"{os.getenv('BASE_URL','').rstrip('/')}/download?path={quote(sum_path)}") if (os.getenv('BASE_URL') and sum_path) else None
       }
    })

# -------- أدوات مقاطع + SRT/VTT --------
def _fmt_hhmmss(t: float) -> str:
    ms = int(round(t * 1000))
    s, ms = divmod(ms, 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def _parse_segments(text: str) -> list:
    segs = []
    for line in (text or "").splitlines():
        line = line.strip()
        # [12.34→56.78] (اسم/متكلم 1) النص
        m = re.match(r"^\[(\d+(?:\.\d+)?)\s*[\u2192\-\>]\s*(\d+(?:\.\d+)?)\]\s*\((.*?)\)\s*(.+)$", line)
        if m:
            st = float(m.group(1)); en = float(m.group(2))
            who = m.group(3).strip()
            txt = m.group(4).strip()
            segs.append({"start": st, "end": en, "speaker": who, "text": txt})
    return segs

from typing import Optional, Tuple
def _write_srt_vtt(segments: list, base_txt_path: str) -> Tuple[Optional[str], Optional[str]]:
    if not base_txt_path:
        return None, None
    p = pathlib.Path(base_txt_path)
    srt = p.with_suffix(".srt")
    vtt = p.with_suffix(".vtt")
    # حضّر السطور مرة واحدة
    srt_lines = []
    vtt_lines = ["WEBVTT", ""]
    for i, s in enumerate(segments, 1):
        t0s = _fmt_hhmmss(s['start']); t1s = _fmt_hhmmss(s['end'])
        label = f"({s.get('speaker','')}) " if s.get("speaker") else ""
        text = (label + s.get("text","")).strip()
        srt_lines += [str(i), f"{t0s} --> {t1s}", text, ""]
        vtt_lines += [f"{t0s.replace(',','.') } --> {t1s.replace(',','.')}", text, ""]
    # اكتب الملفين
    try:
        with open(srt, "w", encoding="utf-8") as f: f.write("\n".join(srt_lines))
    except Exception: srt = None
    try:
        with open(vtt, "w", encoding="utf-8") as f: f.write("\n".join(vtt_lines))
    except Exception: vtt = None
    return srt.as_posix() if srt else None, vtt.as_posix() if vtt else None

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
async def transcribe(
    file: UploadFile = File(...),
    audio: UploadFile = File(None),
    model_name: Optional[str] = Form(None),
    enhance: bool = Form(True),
    whisper_mode: str = Form("normal"),   # "normal" | "whisper"
    diarize: bool = Form(True),
    auto_k: bool = Form(True),
    max_speakers: int = Form(2),
    enroll_threshold: float = Form(0.65),
    device_sel: str = Form("auto"),       # "auto" | "cpu" | "cuda"
    compute_sel: str = Form("auto"),      # "auto" | "int8" | "float16" | "float32"
    summary_mode: str = Form("off"),  # "off" | "lite(mT5)" | "ultra(Jais-13B)"
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    request: Request = None,
):
    # مفتاح API اختياري: يُفعَّل إذا ضُبط المتغير
    if API_TOKEN and (x_api_key or "") != API_TOKEN:
        return _response_error(401, "unauthorized", "invalid api key")
    core = _get_core()
    uf = file or audio
    if uf is None:
        return _response_error(400, "no_file", "use form field 'file' or 'audio'")
    globals()["_SUMMARY_SOURCE"] = "local"
    try:
        logger.info(f"[REQ] model_name={model_name or core.DEFAULT_MODEL} device_sel={device_sel} compute_sel={compute_sel} diarize={diarize} summary_mode={summary_mode}")
    except Exception: pass
    
    tmpdir = tempfile.mkdtemp(prefix="asr_")
    try:
        dst = pathlib.Path(tmpdir) / ((uf.filename) or "audio.wav")
        with open(dst, "wb") as f:
            shutil.copyfileobj(uf.file, f)
           # حجم وحد أقصى
        try:
            if dst.stat().st_size > MAX_UPLOAD_MB * 1024 * 1024:
                return _response_error(413, "file_too_large", f"max={MAX_UPLOAD_MB}MB")
        except Exception:
            pass
        # رفض امتداد غير مدعوم
        if pathlib.Path(dst).suffix.lower() not in ALLOWED_EXT:
            return _response_error(415, "unsupported_media_type", pathlib.Path(dst).suffix.lower())

        try:
            # asr_core.process يُتوقع أن يعيد 3 أو 6 عناصر
            result = core.process(
                str(dst),
                model_name or core.DEFAULT_MODEL,
                enhance, whisper_mode, diarize, auto_k, max_speakers,
                enroll_threshold, device_sel, compute_sel, "off",  # تعطيل تلخيص core افتراضيًا
                punctuate=True
            )

            # توحيد الحقول
            if isinstance(result, dict):
                txt = result.get("text","")
                out_path = result.get("txt_path")
                summary_text = result.get("summary","") or ""
                keywords = result.get("keywords","") or ""
                sum_path = result.get("summary_path")
            elif isinstance(result, (list, tuple)):
                # توافق قديم
                if len(result) == 6:
                    txt, out_path, _dl1, summary_text, keywords, sum_path = result
                elif len(result) == 3:
                    txt, out_path, _dl1 = result
                    summary_text, keywords, sum_path = "", "", None
                else:
                    return _response_error(500, "unexpected_result_shape", f"got {len(result)} items")
            else:
                return _response_error(500, "unexpected_result_type")

            # ترقيم المتكلمين
            txt = _renumber_speakers(txt or "")

            # إجبار عدم التلخيص داخل /transcribe دائماً
            summary_mode = "off"
            if False and summary_mode and summary_mode.lower() != "off":
                if not summary_text:
                    try:
                        s_text, kw_csv = _summarize(txt, mode=summary_mode)
                    except HTTPException as he:
                        # مرّر كـ استجابة FastAPI القياسية
                        raise he
                    summary_text = s_text
                    keywords = kw_csv
                try:
                    if (summary_text or "").strip():
                        sum_path = str(pathlib.Path(out_path).with_suffix(".summary.txt"))
                        pathlib.Path(sum_path).write_text(
                            summary_text + (("\n\nالكلمات المفتاحية: " + (keywords or "")) if keywords else ""),
                            encoding="utf-8"
                        )
                except Exception as e:
                    print(f"[WRITE_SUMMARY] {e}")
            else:
                globals()["_SUMMARY_SOURCE"] = "off"
            # استعمل مخرجات core إن وُجدت، وإلا اسقط إلى التوليد
            segments = (result.get("segments") if isinstance(result, dict) else None) or _parse_segments(txt)
            srt_path = (result.get("srt_path") if isinstance(result, dict) else None)
            vtt_path = (result.get("vtt_path") if isinstance(result, dict) else None)
            seg_path = (result.get("segments_path") if isinstance(result, dict) else None)
            if not srt_path or not vtt_path:
                _srt2, _vtt2 = _write_srt_vtt(segments, out_path)
                srt_path = srt_path or _srt2
                vtt_path = vtt_path or _vtt2
            if not seg_path:
                seg_path = _write_segments_json(segments, out_path)
            return _response_ok(txt, summary_text, keywords, out_path, sum_path, segments, srt_path, vtt_path, seg_path)

        except HTTPException as he:
            # أعدّ تمرير أخطاء HTTP (503 مثلاً)
            raise he
        except Exception:
            # تتبّع كامل مفيد لتشخيص WinError 233 وغيرها
            return _response_error(500, "processing_failed", traceback.format_exc())

    finally:
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass

@app.post("/transcribe-batch")
async def transcribe_batch(
    files: List[UploadFile] = File(...),
    model_name: Optional[str] = Form(None),
    enhance: bool = Form(True),
    whisper_mode: str = Form("normal"),
    diarize: bool = Form(True),
    auto_k: bool = Form(True),
    max_speakers: int = Form(2),
    enroll_threshold: float = Form(0.65),
    device_sel: str = Form("auto"),
    compute_sel: str = Form("auto"),
    summary_mode: str = Form("off"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    request: Request = None,
):
    if API_TOKEN and (x_api_key or "") != API_TOKEN:
        return _response_error(401, "unauthorized", "invalid api key")
    core = _get_core()
    globals()["_SUMMARY_SOURCE"] = "local"

    tmpdir = tempfile.mkdtemp(prefix="asr_batch_")
    try:
        saved: List[str] = []
        for uf in files:
            dst = pathlib.Path(tmpdir) / (uf.filename or f"audio_{len(saved)}.wav")
            with open(dst, "wb") as f:
                shutil.copyfileobj(uf.file, f)
            saved.append(str(dst))

        try:
            result = core.process_many(
                saved,
                model_name or core.DEFAULT_MODEL,
                enhance, whisper_mode, diarize, auto_k, max_speakers,
                enroll_threshold, device_sel, compute_sel, "off", punctuate=True
            )

            if isinstance(result, dict):
                merged_text = result.get("text","")
                merged_path = result.get("txt_path")
                merged_sum = result.get("summary","") or ""
                keywords = result.get("keywords","") or ""
                merged_sum_path = result.get("summary_path")
            elif isinstance(result, (list, tuple)):
                # توافق قديم
                if len(result) == 6:
                    merged_text, merged_path, _dl1, merged_sum, keywords, merged_sum_path = result
                elif len(result) == 3:
                    merged_text, merged_path, _dl1 = result
                    merged_sum, merged_sum_path, keywords = "", None, ""
                else:
                    return _response_error(500, "unexpected_result_shape", f"got {len(result)} items")
            else:
                return _response_error(500, "unexpected_result_type")

            # ترقيم
            merged_text = _renumber_speakers(merged_text or "")

            if summary_mode and summary_mode.lower() != "off":
                if not (merged_sum or "").strip():
                    try:
                        s_text, kw_csv = _summarize(merged_text, mode=summary_mode)
                    except HTTPException as he:
                        raise he
                    merged_sum, keywords = s_text, kw_csv
                try:
                    if (merged_sum or "").strip():
                        merged_sum_path = str(pathlib.Path(merged_path).with_suffix(".summary.txt"))
                        pathlib.Path(merged_sum_path).write_text(
                            merged_sum + (("\n\nالكلمات المفتاحية: " + (keywords or "")) if keywords else ""),
                            encoding="utf-8"
                        )
                except Exception as e:
                    print(f"[WRITE_SUMMARY_BATCH] {e}")
            else:
                globals()["_SUMMARY_SOURCE"] = "off"

            # دمج: اسقط إلى التوليد لأن core لا يعيد مسار JSON/ترجمات مدمجة
            segs = _parse_segments(merged_text)
            srt_path, vtt_path = _write_srt_vtt(segs, merged_path)
            seg_path = _write_segments_json(segs, merged_path)
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
    if API_TOKEN and (x_api_key or "") != API_TOKEN:
        return _response_error(401, "unauthorized", "invalid api key")
    try:
        base = OUTPUTS_DIR
        p = pathlib.Path(path).expanduser().resolve()
        if base not in p.parents and base != p.parent:
            return _response_error(403, "forbidden_path", "outside outputs/")
        if not p.exists() or not p.is_file():
            return _response_error(404, "file_not_found", p.as_posix())
        # حظر الامتدادات غير المسموح تنزيلها
        if p.suffix.lower() not in _DOWNLOAD_ALLOW:
            return _response_error(403, "forbidden_extension", p.suffix.lower())
        return FileResponse(p.as_posix(), media_type="text/plain", filename=p.name)
    except Exception as e:
        return _response_error(500, "download_failed", str(e))
    
@app.get("/export.srt")
def export_srt(path: str = Query(..., description="Absolute or outputs-relative path to txt transcript"),
               x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    if API_TOKEN and (x_api_key or "") != API_TOKEN:
        return _response_error(401, "unauthorized", "invalid api key")
    try:
        base = OUTPUTS_DIR
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
            srt_path, _ = _write_srt_vtt(segs, p.as_posix())
        if not srt_path:
            return _response_error(500, "srt_failed")
        return FileResponse(srt_path, media_type="application/x-subrip", filename=pathlib.Path(srt_path).name)
    except Exception as e:
        return _response_error(500, "srt_failed", str(e))

@app.get("/export.vtt")
def export_vtt(path: str = Query(..., description="Absolute or outputs-relative path to txt transcript"),
               x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    if API_TOKEN and (x_api_key or "") != API_TOKEN:
        return _response_error(401, "unauthorized", "invalid api key")
    try:
        base = OUTPUTS_DIR
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
            _, vtt_path = _write_srt_vtt(segs, p.as_posix())
        if not vtt_path:
            return _response_error(500, "vtt_failed")
        return FileResponse(vtt_path, media_type="text/vtt", filename=pathlib.Path(vtt_path).name)
    except Exception as e:
        return _response_error(500, "vtt_failed", str(e))    

@app.get("/segments")
def segments_json(path: str = Query(..., description="Absolute or outputs-relative path to txt transcript"),
                  x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
                  request: Request = None):
    if API_TOKEN and (x_api_key or "") != API_TOKEN:
        return _response_error(401, "unauthorized", "invalid api key")
    base = OUTPUTS_DIR
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
    if API_TOKEN and (x_api_key or "") != API_TOKEN:
        return _response_error(401, "unauthorized", "invalid api key")
    base = OUTPUTS_DIR
    p = pathlib.Path(path).expanduser().resolve()
    if base not in p.parents and base != p.parent:
        return _response_error(403, "forbidden_path", "outside outputs/")
    if not p.exists() or not p.is_file():
        return _response_error(404, "file_not_found", p.as_posix())
    txt = p.read_text(encoding="utf-8", errors="ignore")
    segs = _parse_segments(txt)
    fname = pathlib.Path(p).with_suffix(".segments.json").name
    return Response(
        content=json.dumps(segs, ensure_ascii=False),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'}
    )

@app.get("/models")
def get_available_models():
    try:
        core = _get_core()
        return {
            "models": getattr(core, "MODEL_CHOICES", ["light", "heavy"]),
            "default": getattr(core, "DEFAULT_MODEL", _DEFAULT_MODEL),
        }
    except Exception:
        return {"models": ["light", "heavy"], "default": _DEFAULT_MODEL}

@app.post("/enroll-speaker")
async def enroll_speaker(
    name: str = Form(...),
    files: List[UploadFile] = File(...),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    if API_TOKEN and (x_api_key or "") != API_TOKEN:
       return _response_error(401, "unauthorized", "invalid api key")
    core = _get_core()
    tmpdir = tempfile.mkdtemp(prefix="enroll_")
    try:
        saved_files: List[str] = []
        for uf in files:
            dst = pathlib.Path(tmpdir) / (uf.filename or f"voice_{len(saved_files)}.wav")
            with open(dst, "wb") as f:
                shutil.copyfileobj(uf.file, f)
            try:
                if dst.stat().st_size > MAX_UPLOAD_MB * 1024 * 1024:
                    return _response_error(413, "file_too_large", f"max={MAX_UPLOAD_MB}MB")
            except Exception:
                pass
            if pathlib.Path(dst).suffix.lower() not in ALLOWED_EXT:
                return _response_error(415, "unsupported_media_type", pathlib.Path(dst).suffix.lower())   
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
    if API_TOKEN and (x_api_key or "") != API_TOKEN:
        return _response_error(401, "unauthorized", "invalid api key")
    try:
        core = _get_core()
        speakers = core.load_enrolled()
        return {"speakers": speakers}
    except Exception as e:
        return _response_error(500, "failed_to_load_speakers", str(e))
    