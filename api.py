# api.py - نسخة مستقرة مُحسّنة
import os, tempfile, shutil, pathlib, re, math, collections, subprocess, json, traceback
from typing import List, Tuple, Optional, Set
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, Header
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse

app = FastAPI(title="Arabic ASR API", version="0.1.2")

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

# api.py
allow = os.getenv("ASR_ALLOWED_ORIGINS", "").split(",") if os.getenv("ASR_ALLOWED_ORIGINS") else []
app.add_middleware(CORSMiddleware, allow_origins=allow or ["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# افتراضيات
_DEFAULT_MODEL = os.getenv("WHISPER_MODEL", "small")
_HAS_CUDA = False

# إعدادات Ollama
_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "")
_ENABLE_OLLAMA = os.getenv("ENABLE_OLLAMA_SUMMARY", "1") in ("1", "true", "True")
_OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT_SECS", "90"))
_SUMMARY_SOURCE = "local"  # سيتم ضبطه أثناء التنفيذ
API_TOKEN = os.getenv("API_TOKEN", "").strip()
MAX_UPLOAD_MB = float(os.getenv("MAX_UPLOAD_MB", "50"))
ALLOWED_EXT = {".wav",".mp3",".m4a",".mp4",".ogg",".flac",".webm",".aac",".3gp"}

def _get_core():
    try:
        import asr_core
        return asr_core
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"ASR core unavailable: {e}")
    
@app.delete("/delete-speaker")
def delete_speaker(name: str = Query(...), x_api_key: Optional[str] = Header(None)):
    if API_TOKEN and (x_api_key or "") != API_TOKEN:
        return _response_error(401, "unauthorized", "invalid api key")
    core = _get_core()
    ok, msg = core.delete_speaker(name)
    return {"success": bool(ok), "message": msg}

@app.get("/speaker-files")
def speaker_files(name: str = Query(...), x_api_key: Optional[str] = Header(None)):
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
        return {
            "status": "ok",
            "model_default": getattr(core, "DEFAULT_MODEL", _DEFAULT_MODEL),
            "cuda": getattr(core, "_HAS_CUDA", _HAS_CUDA),
            "ollama_enabled": _ENABLE_OLLAMA,
            "ffmpeg": ffmpeg_ok,
        }
    except Exception:
        return {
            "status": "ok",
            "model_default": _DEFAULT_MODEL,
            "cuda": _HAS_CUDA,
            "ollama_enabled": _ENABLE_OLLAMA,
            "ffmpeg": False,
        }

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

def _sent_split_ar(text: str) -> list:
    parts = re.split(r"[\.!\?؟\n]+", text)
    return [p.strip() for p in parts if p.strip()]

def _score_sentence(sent: str, freq: dict) -> float:
    toks = _tokenize_ar(sent)
    if not toks: return 0.0
    return sum(freq.get(t, 0) for t in toks) / max(1.0, math.sqrt(len(toks)))

def _shorten_sentence(sent: str, max_len: int = 20) -> str:
    toks = sent.split()
    return " ".join(toks[:max_len]) + ("..." if len(toks) > max_len else "")

def _summarize_local(text: str, max_lines: int = 4) -> str:
    t = _clean_for_summary(text)
    sents = _sent_split_ar(t)
    if not sents:
        return ""
    bag = []
    for s in sents:
        bag += _tokenize_ar(s)
    if not bag:
        return "\n".join(f"- {_shorten_sentence(s)}" for s in sents[:max_lines])
    freq = collections.Counter(bag)
    scored = [(i, _score_sentence(s, freq), s) for i, s in enumerate(sents)]
    top = sorted(sorted(scored, key=lambda x: x[1], reverse=True)[:max_lines], key=lambda x: x[0])
    return "\n".join(f"- {_shorten_sentence(t[2])}" for t in top)

def _has_ollama() -> bool:
    if not _ENABLE_OLLAMA:
        return False
    try:
        subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=3, check=True)
        return True
    except Exception:
        return False

def _available_ollama_models() -> Set[str]:
    try:
        out = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5, check=True).stdout
        names = []
        for line in (out or "").splitlines():
            line = line.strip()
            if not line or line.startswith("NAME"):
                continue
            parts = line.split()
            if parts:
                names.append(parts[0])
        return set(names)
    except Exception:
        return set()

def _summarize_ollama(text: str, max_lines: int = 5, model: Optional[str] = None, prefs: Optional[List[str]] = None) -> str:
    order: List[str] = []
    if model: order.append(model)
    if _OLLAMA_MODEL: order.append(_OLLAMA_MODEL)
    if prefs: order.extend([m for m in prefs if m not in order])

    have = _available_ollama_models()
    prompt = (
        f"لخّص النص التالي بدقة في {max_lines} نقاط قصيرة.\n"
        f"ثم أعطني 8 كلمات مفتاحية بالعربية مفصولة بفواصل فقط.\n\n"
        f"النص:\n{text}\n\n"
        f"النقاط:\n- \n- \n- \n- \n\n"
        f"الكلمات المفتاحية:\n"
    )
    for m in order:
        if m not in have:
            continue
        try:
            res = subprocess.run(["ollama", "run", m, prompt],
                                 capture_output=True, text=True, timeout=_OLLAMA_TIMEOUT)
            out = (res.stdout or "").strip()
            if out:
                globals()["_SUMMARY_SOURCE"] = m
                return out
            # debug الخرج الفارغ
            err = (res.stderr or "").strip()
            if err:
                print(f"[OLLAMA:{m}] stderr: {err[:200]}")
        except Exception as e:
            print(f"[OLLAMA:{m}] exception: {e}")
            continue
    return ""

def _summarize(text: str, mode: str = "auto") -> Tuple[str, str]:
    if not text or not mode or mode.lower() == "off":
        globals()["_SUMMARY_SOURCE"] = "off"
        return ("", "")
    clean = _clean_for_summary(text)
    mode = mode.lower()
    if _has_ollama():
        if mode == "lite":
            prefs = ["phi"]
        elif mode == "medium":
            prefs = ["gemma:2b-instruct"]
        elif mode == "heavy":
            prefs = ["mistral:latest"]
        elif mode == "xlarge":
            prefs = ["qwen2.5:7b-instruct"]
        else:
            prefs = ["phi", "gemma:2b-instruct", "mistral:latest", "qwen2.5:7b-instruct"]
        s = _summarize_ollama(clean, max_lines=5, prefs=prefs) if prefs else ""
        if s:
            m = (re.search(r"الكلمات\s*المفتاحية\s*[:：]\s*(.+)$", s, re.M) or
                 re.search(r"Keywords\s*[:：]\s*(.+)$", s, re.I | re.M))
            if m:
                kw_line = re.sub(r"^[\-\*\•]\s*", "", m.group(1).strip())
                return (s, kw_line)
            return (s, ", ".join(_keywords_ar(clean, k=10)))
    # محلي
    globals()["_SUMMARY_SOURCE"] = "local"
    return (_summarize_local(clean, max_lines=4), ", ".join(_keywords_ar(clean, k=10)))

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
                 srt_path: Optional[str] = None, vtt_path: Optional[str] = None) -> JSONResponse:
    base_url = os.getenv("BASE_URL", "").rstrip("/")
    data = {
        "text": text or "",
        "summary": summary or "",
        "keywords": keywords or "",
        "txt_path": txt_path,
        "summary_path": summary_path,
        "summary_source": globals().get("_SUMMARY_SOURCE", "local"),
        "segments": segments or [],
        "srt_path": srt_path,
        "vtt_path": vtt_path,
    }
    if base_url and txt_path:
        data["download_urls"] = {
            "txt":  f"{base_url}/download?path={txt_path}",
            "srt":  f"{base_url}/download?path={srt_path}" if srt_path else None,
            "vtt":  f"{base_url}/download?path={vtt_path}" if vtt_path else None,
            "summary": f"{base_url}/download?path={summary_path}" if summary_path else None,
        }
    return JSONResponse(data)

def _response_error(code: int, err: str, detail: Optional[str] = None) -> JSONResponse:
    # يحافظ على المخطط حتى في الخطأ
    payload = {
        "error": err,
        "detail": detail or "",
        "text": "",
        "summary": "",
        "keywords": "",
        "txt_path": None,
        "summary_path": None,
        "summary_source": globals().get("_SUMMARY_SOURCE", "local"),
    }
    return JSONResponse(payload, status_code=code)

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

def _write_srt_vtt(segments: list, base_txt_path: str) -> tuple[str, str]:
    if not base_txt_path:
        return None, None
    p = pathlib.Path(base_txt_path)
    srt = p.with_suffix(".srt")
    vtt = p.with_suffix(".vtt")
    # SRT
    try:
        with open(srt, "w", encoding="utf-8") as f:
            for i, s in enumerate(segments, 1):
                f.write(str(i) + "\n")
                f.write(f"{_fmt_hhmmss(s['start'])} --> {_fmt_hhmmss(s['end'])}\n")
                label = f"({s['speaker']}) " if s.get("speaker") else ""
                f.write(label + s.get("text","") + "\n\n")
    except Exception:
        srt = None
    # VTT
    try:
        with open(vtt, "w", encoding="utf-8") as f:
            f.write("WEBVTT\n\n")
            for s in segments:
                t0 = _fmt_hhmmss(s["start"]).replace(",", ".")
                t1 = _fmt_hhmmss(s["end"]).replace(",", ".")
                label = f"({s['speaker']}) " if s.get("speaker") else ""
                f.write(f"{t0} --> {t1}\n{label}{s.get('text','')}\n\n")
    except Exception:
        vtt = None
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
    model_name: Optional[str] = Form(None),
    enhance: bool = Form(True),
    whisper_mode: str = Form("normal"),   # "normal" | "whisper"
    diarize: bool = Form(True),
    auto_k: bool = Form(True),
    max_speakers: int = Form(2),
    enroll_threshold: float = Form(0.65),
    device_sel: str = Form("auto"),       # "auto" | "cpu" | "cuda"
    compute_sel: str = Form("auto"),      # "auto" | "int8" | "float16" | "float32"
    summary_mode: str = Form("auto"),     # "lite" | "medium" | "heavy" | "xlarge" | "auto" | "off"
    x_api_key: Optional[str] = Header(None),
):
    # مفتاح API اختياري: يُفعَّل إذا ضُبط المتغير
    if API_TOKEN and (x_api_key or "") != API_TOKEN:
        return _response_error(401, "unauthorized", "invalid api key")
    core = _get_core()
    globals()["_SUMMARY_SOURCE"] = "local"

    tmpdir = tempfile.mkdtemp(prefix="asr_")
    try:
        dst = pathlib.Path(tmpdir) / (file.filename or "audio.wav")
        with open(dst, "wb") as f:
            shutil.copyfileobj(file.file, f)
           # حجم وحد أقصى
        try:
            if dst.stat().st_size > MAX_UPLOAD_MB * 1024 * 1024:
                return _response_error(413, "file_too_large", f"max={MAX_UPLOAD_MB}MB")
        except Exception:
            pass
        # امتداد مقبول تنبيهي
        if pathlib.Path(dst).suffix.lower() not in ALLOWED_EXT:
            print(f"[WARN] امتداد غير شائع: {dst.suffix}")    

        try:
            # asr_core.process يُتوقع أن يعيد 3 أو 6 عناصر
            result = core.process(
                str(dst),
                model_name or core.DEFAULT_MODEL,
                enhance, whisper_mode, diarize, auto_k, max_speakers,
                enroll_threshold, device_sel, compute_sel, "off"  # تعطيل تلخيص core افتراضيًا
            )

            summary_text, keywords, sum_path = "", "", None
            if isinstance(result, (list, tuple)):
                if len(result) == 6:
                    txt, out_path, _dl1, core_sum, core_kw, sum_path = result
                    txt = txt or ""
                    # إذا قدّم core تلخيصًا صالحًا، استخدمه وميز المصدر
                    if (core_sum or "").strip():
                        summary_text = core_sum
                        keywords = (core_kw or "").strip()
                        globals()["_SUMMARY_SOURCE"] = "core"
                elif len(result) == 3:
                    txt, out_path, _dl1 = result
                else:
                    return _response_error(500, "unexpected_result_shape", f"got {len(result)} items")
            else:
                return _response_error(500, "unexpected_result_type")

            # ترقيم المتكلمين
            txt = _renumber_speakers(txt or "")

            # تلخيص عند الطلب أو إذا لا يوجد core_sum
            if summary_mode and summary_mode.lower() != "off":
                if not summary_text:
                    s_text, kw_csv = _summarize(txt, mode=summary_mode)
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
                # استنتاج المقاطع من النص وكتابة SRT/VTT
            segments = _parse_segments(txt)
            srt_path, vtt_path = _write_srt_vtt(segments, out_path)
            seg_path = _write_segments_json(segments, out_path)
            resp = _response_ok(txt, summary_text, keywords, out_path, sum_path, segments, srt_path, vtt_path)
            resp.body  # touch
            payload = json.loads(resp.body)
            payload["segments_path"] = seg_path
            return JSONResponse(payload)

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
    summary_mode: str = Form("auto"),
    x_api_key: Optional[str] = Header(None),
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
                enroll_threshold, device_sel, compute_sel, "off"
            )

            keywords = ""
            if isinstance(result, (list, tuple)):
                if len(result) == 6:
                    merged_text, merged_path, _dl1, core_sum, core_kw, merged_sum_path = result
                    merged_text = merged_text or ""
                    if (core_sum or "").strip():
                        merged_sum = core_sum
                        keywords = (core_kw or "").strip()
                        globals()["_SUMMARY_SOURCE"] = "core"
                    else:
                        merged_sum = ""
                elif len(result) == 3:
                    merged_text, merged_path, _dl1 = result
                    merged_sum, merged_sum_path = "", None
                else:
                    return _response_error(500, "unexpected_result_shape", f"got {len(result)} items")
            else:
                return _response_error(500, "unexpected_result_type")

            # ترقيم
            merged_text = _renumber_speakers(merged_text or "")

            if summary_mode and summary_mode.lower() != "off":
                if not (merged_sum or "").strip():
                    s_text, kw_csv = _summarize(merged_text, mode=summary_mode)
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

            segs = _parse_segments(merged_text)
            srt_path, vtt_path = _write_srt_vtt(segs, merged_path)
            seg_path = _write_segments_json(segs, merged_path)
            resp = _response_ok(merged_text, merged_sum, keywords, merged_path, merged_sum_path, segs, srt_path, vtt_path)
            payload = json.loads(resp.body)
            payload["segments_path"] = seg_path
            return JSONResponse(payload)

        except Exception:
            return _response_error(500, "processing_failed", traceback.format_exc())

    finally:
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass

@app.get("/download")
def download_txt(path: str = Query(..., description="Absolute or outputs-relative path to txt file"),
                 x_api_key: Optional[str] = Header(None)):
    if API_TOKEN and (x_api_key or "") != API_TOKEN:
        return _response_error(401, "unauthorized", "invalid api key")
    try:
        base = pathlib.Path("outputs").resolve()
        p = pathlib.Path(path).resolve()
        if base not in p.parents and base != p.parent:
            return _response_error(403, "forbidden_path", "outside outputs/")
        if not p.exists() or not p.is_file():
            return _response_error(404, "file_not_found", p.as_posix())
        return FileResponse(p.as_posix(), media_type="text/plain", filename=p.name)
    except Exception as e:
        return _response_error(500, "download_failed", str(e))
    
@app.get("/export.srt")
def export_srt(path: str = Query(..., description="Absolute or outputs-relative path to txt transcript"),
               x_api_key: Optional[str] = Header(None)):
    if API_TOKEN and (x_api_key or "") != API_TOKEN:
        return _response_error(401, "unauthorized", "invalid api key")
    try:
        base = pathlib.Path("outputs").resolve()
        p = pathlib.Path(path).resolve()
        if base not in p.parents and base != p.parent:
            return _response_error(403, "forbidden_path", "outside outputs/")
        if not p.exists() or not p.is_file():
            return _response_error(404, "file_not_found", p.as_posix())
        txt = p.read_text(encoding="utf-8", errors="ignore")
        segs = _parse_segments(txt)
        srt_path, _ = _write_srt_vtt(segs, p.as_posix())
        if not srt_path:
            return _response_error(500, "srt_failed")
        return FileResponse(srt_path, media_type="text/plain", filename=pathlib.Path(srt_path).name)
    except Exception as e:
        return _response_error(500, "srt_failed", str(e))

@app.get("/export.vtt")
def export_vtt(path: str = Query(..., description="Absolute or outputs-relative path to txt transcript"),
               x_api_key: Optional[str] = Header(None)):
    if API_TOKEN and (x_api_key or "") != API_TOKEN:
        return _response_error(401, "unauthorized", "invalid api key")
    try:
        base = pathlib.Path("outputs").resolve()
        p = pathlib.Path(path).resolve()
        if base not in p.parents and base != p.parent:
            return _response_error(403, "forbidden_path", "outside outputs/")
        if not p.exists() or not p.is_file():
            return _response_error(404, "file_not_found", p.as_posix())
        txt = p.read_text(encoding="utf-8", errors="ignore")
        segs = _parse_segments(txt)
        _, vtt_path = _write_srt_vtt(segs, p.as_posix())
        if not vtt_path:
            return _response_error(500, "vtt_failed")
        return FileResponse(vtt_path, media_type="text/vtt", filename=pathlib.Path(vtt_path).name)
    except Exception as e:
        return _response_error(500, "vtt_failed", str(e))    

@app.get("/models")
def get_available_models():
    try:
        core = _get_core()
        return {
            "models": getattr(core, "MODEL_CHOICES", ["tiny", "base", "small", "medium", "large-v3"]),
            "default": getattr(core, "DEFAULT_MODEL", _DEFAULT_MODEL),
        }
    except Exception:
        return {"models": ["tiny", "base", "small", "medium", "large-v3"], "default": _DEFAULT_MODEL}

@app.post("/enroll-speaker")
async def enroll_speaker(
    name: str = Form(...),
    files: List[UploadFile] = File(...),
    x_api_key: Optional[str] = Header(None),
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
                print(f"[WARN] امتداد غير شائع: {dst.suffix}")    
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
def get_enrolled_speakers(x_api_key: Optional[str] = Header(None)):
    if API_TOKEN and (x_api_key or "") != API_TOKEN:
        return _response_error(401, "unauthorized", "invalid api key")
    try:
        core = _get_core()
        speakers = core.load_enrolled()
        return {"speakers": speakers}
    except Exception as e:
        return _response_error(500, "failed_to_load_speakers", str(e))
