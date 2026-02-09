# routers/transcribe.py
import asyncio
import json
import pathlib
import secrets
import shutil
import tempfile
import traceback
import uuid
from typing import List, Optional

from fastapi import APIRouter, File, Form, Header, Request, UploadFile
from fastapi.responses import JSONResponse

import aiofiles
import nlp_core
from config import settings
from server.deps import (
    get_core,
    response_ok,
    response_error,
    parse_segments,
    write_segments_json,
    JOBS,
    job_file,
    run_transcribe_job_impl,
    limiter,
)

router = APIRouter()


def _check_api_key(x_api_key: Optional[str]):
    if settings.API_TOKEN and not secrets.compare_digest(x_api_key or "", settings.API_TOKEN):
        return response_error(401, "unauthorized", "invalid api key")
    return None


def _resolve_enhance_mode(enhance_mode: str, enhance: bool) -> str:
    """Resolve effective enhance_mode. Backward compat: enhance=True -> full, enhance=False -> use enhance_mode (default off)."""
    if enhance:
        return "full"
    em = (enhance_mode or "off").strip().lower()
    return em if em in ("off", "light", "full") else "off"


# حجم كل chunk عند الرفع التدريجي (1–4 MB)
UPLOAD_CHUNK_SIZE = 2 * 1024 * 1024


@router.post("/transcribe")
@limiter.limit("6/minute")
async def transcribe(
    request: Request,
    file: UploadFile = File(...),
    audio: UploadFile = File(None),
    async_mode: bool = Form(False),
    model_name: Optional[str] = Form(None),
    enhance: bool = Form(False),
    enhance_mode: str = Form("off"),
    enhance_level: str = Form("medium"),
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
):
    err = _check_api_key(x_api_key)
    if err:
        return err
    core = get_core()
    uf = file or audio
    if uf is None:
        return response_error(400, "no_file", "use form field 'file' or 'audio'")
    nlp_core.set_summary_source("local")

    tmpdir = tempfile.mkdtemp(prefix="asr_")
    dst = pathlib.Path(tmpdir) / ((uf.filename) or "audio.wav")
    max_bytes = int(settings.MAX_UPLOAD_MB * 1024 * 1024)
    written = 0
    try:
        async with aiofiles.open(dst, "wb") as f:
            while True:
                chunk = await uf.read(UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    break
                await f.write(chunk)
    except Exception as e:
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass
        return response_error(500, "upload_failed", str(e))

    try:
        if written > max_bytes or dst.stat().st_size > max_bytes:
            try:
                shutil.rmtree(tmpdir)
            finally:
                return response_error(413, "file_too_large", f"max={settings.MAX_UPLOAD_MB}MB")
    except Exception:
        pass
    if dst.suffix.lower() not in settings.ALLOWED_EXT:
        try:
            shutil.rmtree(tmpdir)
        finally:
            return response_error(415, "unsupported_media_type", dst.suffix.lower())

    if not async_mode:
        try:
            em = _resolve_enhance_mode(enhance_mode, enhance)
            result = await asyncio.to_thread(
                core.process,
                str(dst),
                model_name=model_name or settings.WHISPER_MODEL,
                enhance=False,
                enhance_mode=em,
                enhance_level=enhance_level,
                whisper_mode=whisper_mode,
                diarize=diarize,
                auto_k=auto_k,
                max_speakers=max_speakers,
                enroll_threshold=enroll_threshold,
                device_sel=device_sel,
                compute_sel=compute_sel,
                summary_mode="off",
                punctuate=punctuate,
            )
            seg_path = result.get("segments_path") or write_segments_json(
                result.get("segments") or [], result.get("txt_path")
            )
            return response_ok(
                result.get("text", ""),
                result.get("summary", "") or "",
                result.get("keywords", "") or "",
                result.get("txt_path"),
                result.get("summary_path"),
                result.get("segments") or [],
                result.get("srt_path"),
                result.get("vtt_path"),
                seg_path,
            )
        finally:
            try:
                shutil.rmtree(tmpdir)
            except Exception:
                pass

    em = _resolve_enhance_mode(enhance_mode, enhance)
    kwargs = dict(
        model_name=model_name or settings.WHISPER_MODEL,
        enhance=False,
        enhance_mode=em,
        enhance_level=enhance_level,
        whisper_mode=whisper_mode,
        diarize=diarize,
        auto_k=auto_k,
        max_speakers=max_speakers,
        enroll_threshold=enroll_threshold,
        device_sel=device_sel,
        compute_sel=compute_sel,
        summary_mode="off",
        punctuate=punctuate,
    )
    max_queued = getattr(settings, "TRANSCRIBE_MAX_QUEUED", 20)
    active = sum(1 for j in JOBS.values() if isinstance(j, dict) and j.get("status") in ("queued", "running"))
    if active >= max_queued:
        return response_error(429, "rate_limited", f"too many queued or running transcribe jobs (max {max_queued})")
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {"status": "queued", "result_path": None, "error": None}
    asyncio.create_task(run_transcribe_job_impl(job_id, dst, kwargs, get_core))
    base = settings.BASE_URL.rstrip("/") or str(request.base_url).rstrip("/")
    return JSONResponse(
        {
            "job_id": job_id,
            "status": "queued",
            "poll_url": f"{base}/job/{job_id}",
            "result_url": f"{base}/job/{job_id}/download",
        },
        status_code=202,
    )


@router.post("/transcribe-batch")
async def transcribe_batch(
    request: Request,
    files: List[UploadFile] = File(...),
    model_name: Optional[str] = Form(None),
    enhance: bool = Form(False),
    enhance_mode: str = Form("off"),
    enhance_level: str = Form("medium"),
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
):
    from fastapi import HTTPException

    err = _check_api_key(x_api_key)
    if err:
        return err
    core = get_core()
    nlp_core.set_summary_source("local")
    em = _resolve_enhance_mode(enhance_mode, enhance)

    tmpdir = tempfile.mkdtemp(prefix="asr_batch_")
    try:
        saved: List[str] = []
        max_bytes = int(settings.MAX_UPLOAD_MB * 1024 * 1024)
        for uf in files:
            dst = pathlib.Path(tmpdir) / (uf.filename or f"audio_{len(saved)}.wav")
            written = 0
            async with aiofiles.open(dst, "wb") as f:
                while True:
                    chunk = await uf.read(UPLOAD_CHUNK_SIZE)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > max_bytes:
                        break
                    await f.write(chunk)
            if dst.suffix.lower() not in settings.ALLOWED_EXT:
                dst.unlink(missing_ok=True)
                return response_error(415, "unsupported_media_type", dst.suffix.lower())
            if written > max_bytes or dst.stat().st_size > max_bytes:
                dst.unlink(missing_ok=True)
                return response_error(413, "file_too_large", f"max={settings.MAX_UPLOAD_MB}MB")
            saved.append(str(dst))

        try:
            result = await asyncio.to_thread(
                core.process_many,
                saved,
                model_name=model_name or settings.WHISPER_MODEL,
                enhance=False,
                enhance_mode=em,
                enhance_level=enhance_level,
                whisper_mode=whisper_mode,
                diarize=diarize,
                auto_k=auto_k,
                max_speakers=max_speakers,
                enroll_threshold=enroll_threshold,
                device_sel=device_sel,
                compute_sel=compute_sel,
                summary_mode="off",
                punctuate=punctuate,
            )

            if not isinstance(result, dict):
                return response_error(500, "unexpected_result_type")

            merged_text = result.get("text", "")
            merged_path = result.get("txt_path")
            merged_sum = result.get("summary", "") or ""
            keywords = result.get("keywords", "") or ""
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
                            merged_sum
                            + (("\n\nالكلمات المفتاحية: " + (keywords or "")) if keywords else ""),
                            encoding="utf-8",
                        )
                        merged_sum_path = str(sum_p)
                except Exception as e:
                    print(f"[WRITE_SUMMARY_BATCH] {e}")
            else:
                nlp_core.set_summary_source("off")

            segs = result.get("segments") or parse_segments(merged_text)
            srt_path = result.get("srt_path")
            vtt_path = result.get("vtt_path")
            seg_path = result.get("segments_path") or write_segments_json(segs, merged_path)
            return response_ok(
                merged_text,
                merged_sum,
                keywords,
                merged_path,
                merged_sum_path,
                segs,
                srt_path,
                vtt_path,
                seg_path,
            )

        except HTTPException:
            raise
        except Exception:
            return response_error(500, "processing_failed", traceback.format_exc())

    finally:
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass
