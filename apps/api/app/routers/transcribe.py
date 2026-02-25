# routers/transcribe.py
import asyncio
import json
import logging
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
from app import nlp_core
from app.config import settings
from app.features.dashboard.schema import ActivityType
from app.features.dashboard.service import DashboardService
from app.server.deps import (
    get_core,
    response_ok,
    response_error,
    parse_segments,
    write_segments_json,
    JOBS,
    job_file,
    run_transcribe_job_impl,
    limiter,
    check_api_key,
)

router = APIRouter()
logger = logging.getLogger("api.transcribe")


def _resolve_enhance_mode(enhance_mode: str, enhance: bool) -> str:
    """Resolve effective enhance_mode. Backward compat: enhance=True -> full, enhance=False -> use enhance_mode (default off)."""
    if enhance:
        return "full"
    effective_mode = (enhance_mode or "off").strip().lower()
    return effective_mode if effective_mode in ("off", "light", "full") else "off"


async def _upload_file_to_temp(upload_file: UploadFile, max_size_mb: float) -> tuple[pathlib.Path, Optional[JSONResponse]]:
    """Upload file to temporary directory with size validation.
    
    Returns:
        Tuple of (temp_file_path, error_response). If error_response is not None, upload failed.
    """
    tmpdir = tempfile.mkdtemp(prefix="asr_")
    dst = pathlib.Path(tmpdir) / (upload_file.filename or "audio.wav")
    max_bytes = int(max_size_mb * 1024 * 1024)
    written_bytes = 0
    
    try:
        async with aiofiles.open(dst, "wb") as f:
            while True:
                chunk = await upload_file.read(settings.UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                written_bytes += len(chunk)
                if written_bytes > max_bytes:
                    break
                await f.write(chunk)
    except (IOError, OSError) as io_error:
        logger.error("File upload IO error: %s", io_error)
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except OSError as cleanup_error:
            logger.warning("Failed to cleanup temp dir %s: %s", tmpdir, cleanup_error)
        return None, response_error(500, "upload_failed", f"IO error: {str(io_error)}")
    except Exception as unexpected_error:
        logger.exception("Unexpected error during file upload: %s", unexpected_error)
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except OSError:
            pass
        return None, response_error(500, "upload_failed", str(unexpected_error))

    # Validate size
    try:
        if written_bytes > max_bytes or dst.stat().st_size > max_bytes:
            shutil.rmtree(tmpdir, ignore_errors=True)
            return None, response_error(413, "file_too_large", f"max={max_size_mb}MB")
    except OSError as stat_error:
        logger.warning("Failed to check file size: %s", stat_error)
    
    # Validate extension
    if dst.suffix.lower() not in settings.ALLOWED_EXT:
        shutil.rmtree(tmpdir, ignore_errors=True)
        return None, response_error(415, "unsupported_media_type", dst.suffix.lower())
    
    return dst, None


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
    user_email: Optional[str] = Form(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    auth_error = check_api_key(x_api_key)
    if auth_error:
        return auth_error
    core = get_core()
    upload_file = file or audio
    if upload_file is None:
        return response_error(400, "no_file", "use form field 'file' or 'audio'")
    nlp_core.set_summary_source("local")

    # Upload file to temp directory with validation
    temp_file_path, upload_error = await _upload_file_to_temp(upload_file, settings.MAX_UPLOAD_MB)
    if upload_error:
        return upload_error

    # استخدام القيم الافتراضية من الإعدادات إذا لم يتم التحديد
    if not enhance_mode:
        enhance_mode = settings.ENHANCE_MODE
    if not enhance_level:
        enhance_level = settings.ENHANCE_LEVEL
    effective_enhance_mode = _resolve_enhance_mode(enhance_mode, enhance)
    
    if not async_mode:
        # Synchronous processing: wait for result
        try:
            sync_job_id = str(uuid.uuid4())
            result = await asyncio.to_thread(
                core.process,
                str(temp_file_path),
                model_name=model_name or settings.WHISPER_MODEL,
                enhance=enhance,
                enhance_mode=effective_enhance_mode,
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
                job_id=sync_job_id,
            )
            if user_email:
                try:
                    DashboardService.record_activity(
                        user_email=user_email,
                        activity_type=ActivityType.ASR,
                        description="transcribe completed",
                        metadata={"mode": "sync", "job_id": sync_job_id},
                    )
                except Exception:
                    pass
            segments_path = result.get("segments_path") or write_segments_json(
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
                segments_path,
                job_id=result.get("job_id", sync_job_id),
                timings_ms=result.get("timings_ms"),
            )
        finally:
            try:
                shutil.rmtree(temp_file_path.parent, ignore_errors=True)
            except OSError as cleanup_error:
                logger.warning("Failed to cleanup temp dir: %s", cleanup_error)

    # Async processing: queue job and return immediately
    job_id = str(uuid.uuid4())
    job_kwargs = dict(
        model_name=model_name or settings.WHISPER_MODEL,
        enhance=enhance,
        enhance_mode=effective_enhance_mode,
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
        job_id=job_id,
    )
    max_queued = getattr(settings, "TRANSCRIBE_MAX_QUEUED", 20)
    active_jobs = sum(1 for j in JOBS.values() if isinstance(j, dict) and j.get("status") in ("queued", "running"))
    if active_jobs >= max_queued:
        return response_error(429, "rate_limited", f"too many queued or running transcribe jobs (max {max_queued})")
    JOBS[job_id] = {"status": "queued", "result_path": None, "error": None}
    asyncio.create_task(run_transcribe_job_impl(job_id, temp_file_path, job_kwargs, get_core))
    if user_email:
        try:
            DashboardService.record_activity(
                user_email=user_email,
                activity_type=ActivityType.ASR,
                description="transcribe queued",
                metadata={"mode": "async", "job_id": job_id},
            )
        except Exception:
            pass
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
    enhance_mode: str = Form(None),
    enhance_level: str = Form(None),
    whisper_mode: str = Form("normal"),
    diarize: bool = Form(True),
    punctuate: bool = Form(False),
    auto_k: bool = Form(True),
    max_speakers: int = Form(2),
    enroll_threshold: float = Form(0.65),
    device_sel: str = Form("auto"),
    compute_sel: str = Form("auto"),
    summary_mode: str = Form("off"),
    user_email: Optional[str] = Form(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    from fastapi import HTTPException

    auth_error = check_api_key(x_api_key)
    if auth_error:
        return auth_error
    core = get_core()
    nlp_core.set_summary_source("local")
    # استخدام القيم الافتراضية من الإعدادات إذا لم يتم التحديد
    if not enhance_mode:
        enhance_mode = settings.ENHANCE_MODE
    if not enhance_level:
        enhance_level = settings.ENHANCE_LEVEL
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
                    chunk = await uf.read(settings.UPLOAD_CHUNK_SIZE)
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
            batch_job_id = str(uuid.uuid4())
            result = await asyncio.to_thread(
                core.process_many,
                saved,
                model_name=model_name or settings.WHISPER_MODEL,
                enhance=enhance,
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
                job_id=batch_job_id,
            )

            if not isinstance(result, dict):
                return response_error(500, "unexpected_result_type")

            if user_email:
                try:
                    DashboardService.record_activity(
                        user_email=user_email,
                        activity_type=ActivityType.ASR,
                        description="batch transcribe completed",
                        metadata={"files_count": len(saved)},
                    )
                except Exception:
                    pass

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
                job_id=result.get("job_id", batch_job_id),
                timings_ms=result.get("timings_ms"),
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
