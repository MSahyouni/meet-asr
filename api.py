# api.py
import os, tempfile, shutil, pathlib
from typing import List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse

app = FastAPI(title="Arabic ASR API", version="0.1.0")

# السماح مؤقتًا بكل الأصول أثناء التطوير (عدّلها لاحقًا)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# قيم خفيفة لاجتياز CI حتى لو asr_core غير متاح أثناء الاستيراد
_DEFAULT_MODEL = os.getenv("WHISPER_MODEL", "base")
_HAS_CUDA = False

def _get_core():
    """استيراد كسول لتفادي فشل import api في بيئات CI."""
    try:
        import asr_core  # يُستورد فقط عند الحاجة
        return asr_core
    except Exception as e:
        # في التشغيل الحقيقي يجب توفر المتطلبات؛ في CI يكفي نجاح import api
        raise HTTPException(status_code=503, detail=f"ASR core unavailable: {e}")

@app.get("/health")
def health():
    # نحاول قراءة معلومات حقيقية من asr_core، وإلا نعيد الافتراضيات الخفيفة
    try:
        import asr_core
        return {
            "status": "ok",
            "model_default": getattr(asr_core, "DEFAULT_MODEL", _DEFAULT_MODEL),
            "cuda": getattr(asr_core, "_HAS_CUDA", _HAS_CUDA),
        }
    except Exception:
        return {"status": "ok", "model_default": _DEFAULT_MODEL, "cuda": _HAS_CUDA}

@app.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    model_name: str = Form(None),
    enhance: bool = Form(True),
    whisper_mode: str = Form("normal"),     # "normal" | "whisper"
    diarize: bool = Form(True),
    auto_k: bool = Form(True),
    max_speakers: int = Form(2),
    enroll_threshold: float = Form(0.65),
    device_sel: str = Form("auto"),         # "auto" | "cpu" | "cuda"
    compute_sel: str = Form("auto"),        # "auto" | "int8" | "float16" | "float32"
    summary_mode: str = Form("best"),       # "best" | "fast" | "off"
):
    core = _get_core()

    tmpdir = tempfile.mkdtemp(prefix="asr_")
    dst = pathlib.Path(tmpdir) / file.filename
    with open(dst, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        txt, out_path, _, summary_text, keywords, sum_path = core.process(
            str(dst),
            model_name or core.DEFAULT_MODEL,
            enhance, whisper_mode, diarize, auto_k, max_speakers,
            enroll_threshold, device_sel, compute_sel, summary_mode
        )
        return JSONResponse({
            "text": txt,
            "summary": summary_text,
            "keywords": keywords,
            "txt_path": out_path,      # مسار على السيرفر (اختياري)
            "summary_path": sum_path,  # إن وُجد
        })
    finally:
        # اترك ملفات outputs/ كما هي (core يكتب داخل outputs/)
        # ويمكن حذف tmpdir لو حبيت
        pass

@app.post("/transcribe-batch")
async def transcribe_batch(
    files: List[UploadFile] = File(...),
    model_name: str = Form(None),
    enhance: bool = Form(True),
    whisper_mode: str = Form("normal"),
    diarize: bool = Form(True),
    auto_k: bool = Form(True),
    max_speakers: int = Form(2),
    enroll_threshold: float = Form(0.65),
    device_sel: str = Form("auto"),
    compute_sel: str = Form("auto"),
    summary_mode: str = Form("best"),
):
    core = _get_core()

    tmpdir = tempfile.mkdtemp(prefix="asr_batch_")
    saved: list[str] = []
    for uf in files:
        dst = pathlib.Path(tmpdir) / uf.filename
        with open(dst, "wb") as f:
            shutil.copyfileobj(uf.file, f)
        saved.append(str(dst))

    try:
        merged_text, merged_path, _, merged_sum, _, merged_sum_path = core.process_many(
            saved,
            model_name or core.DEFAULT_MODEL,
            enhance, whisper_mode, diarize, auto_k, max_speakers,
            enroll_threshold, device_sel, compute_sel, summary_mode
        )
        return JSONResponse({
            "text": merged_text,
            "summary": merged_sum,
            "txt_path": merged_path,
            "summary_path": merged_sum_path,
        })
    finally:
        pass

@app.get("/download")
def download_txt(path: str):
    # تنزيل ملف TXT محفوظ في outputs/
    p = pathlib.Path(path)
    if not p.exists() or not p.is_file():
        return JSONResponse({"error": "file not found"}, status_code=404)
    return FileResponse(p.as_posix(), media_type="text/plain", filename=p.name)
