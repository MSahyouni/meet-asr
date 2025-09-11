# api.py
import os, tempfile, shutil, pathlib
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse

from asr_core import process, process_many, MODEL_CHOICES, DEFAULT_MODEL, _HAS_CUDA

app = FastAPI(title="Arabic ASR API", version="0.1.0")

# اسمح بالوصول من أي أصل أثناء التطوير (عدلو لاحقاً)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok", "model_default": DEFAULT_MODEL, "cuda": _HAS_CUDA}

@app.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    model_name: str = Form(DEFAULT_MODEL),
    enhance: bool = Form(True),
    whisper_mode: str = Form("normal"),     # "normal" | "whisper"
    diarize: bool = Form(True),
    auto_k: bool = Form(True),
    max_speakers: int = Form(2),
    enroll_threshold: float = Form(0.65),
    device_sel: str = Form("auto"),         # "auto" | "cpu" | "cuda"
    compute_sel: str = Form("auto"),        # "auto" | "int8" | "float16" | "float32"
):
    # خزّن الملف مؤقتاً على القرص
    tmpdir = tempfile.mkdtemp(prefix="asr_")
    try:
        dst = pathlib.Path(tmpdir) / file.filename
        with open(dst, "wb") as f:
            shutil.copyfileobj(file.file, f)

        txt, out_path, _ = process(
            str(dst), model_name, enhance, whisper_mode, diarize, auto_k, max_speakers,
            enroll_threshold, device_sel, compute_sel
        )
        return JSONResponse({
            "text": txt,
            "txt_path": out_path,  # مسار على السيرفر (اختياري)
        })
    finally:
        # لا نحذف مؤقتاً لو بدك تحتفظ بالـ outputs/
        pass

@app.post("/transcribe-batch")
async def transcribe_batch(
    files: List[UploadFile] = File(...),
    model_name: str = Form(DEFAULT_MODEL),
    enhance: bool = Form(True),
    whisper_mode: str = Form("normal"),
    diarize: bool = Form(True),
    auto_k: bool = Form(True),
    max_speakers: int = Form(2),
    enroll_threshold: float = Form(0.65),
    device_sel: str = Form("auto"),
    compute_sel: str = Form("auto"),
):
    tmpdir = tempfile.mkdtemp(prefix="asr_batch_")
    saved = []
    try:
        for uf in files:
            dst = pathlib.Path(tmpdir) / uf.filename
            with open(dst, "wb") as f:
                shutil.copyfileobj(uf.file, f)
            saved.append(str(dst))

        txt, out_path, _ = process_many(
            saved, model_name, enhance, whisper_mode, diarize, auto_k, max_speakers,
            enroll_threshold, device_sel, compute_sel
        )
        return JSONResponse({
            "text": txt,
            "txt_path": out_path,
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
