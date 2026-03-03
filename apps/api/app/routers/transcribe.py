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

from fastapi import APIRouter, File, Form, Header, HTTPException, Request, UploadFile
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
    run_transcribe_batch_job_impl,
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


async def _upload_files_to_temp(upload_files: List[UploadFile], max_size_mb: float) -> tuple[Optional[List[pathlib.Path]], Optional[pathlib.Path], Optional[JSONResponse]]:
    """Upload multiple files to one temporary directory with validation.

    Returns:
        Tuple of (saved_paths, tmpdir_path, error_response). If error_response is not None, upload failed.
    """
    tmpdir = pathlib.Path(tempfile.mkdtemp(prefix="asr_batch_"))
    max_bytes = int(max_size_mb * 1024 * 1024)
    saved_paths: List[pathlib.Path] = []

    try:
        for upload_file in upload_files:
            dst = tmpdir / (upload_file.filename or f"audio_{len(saved_paths)}.wav")
            written_bytes = 0
            async with aiofiles.open(dst, "wb") as f:
                while True:
                    chunk = await upload_file.read(settings.UPLOAD_CHUNK_SIZE)
                    if not chunk:
                        break
                    written_bytes += len(chunk)
                    if written_bytes > max_bytes:
                        break
                    await f.write(chunk)

            if dst.suffix.lower() not in settings.ALLOWED_EXT:
                dst.unlink(missing_ok=True)
                shutil.rmtree(tmpdir, ignore_errors=True)
                return None, None, response_error(415, "unsupported_media_type", dst.suffix.lower())

            if written_bytes > max_bytes or dst.stat().st_size > max_bytes:
                dst.unlink(missing_ok=True)
                shutil.rmtree(tmpdir, ignore_errors=True)
                return None, None, response_error(413, "file_too_large", f"max={max_size_mb}MB")

            saved_paths.append(dst)
    except (IOError, OSError) as io_error:
        logger.error("Batch upload IO error: %s", io_error)
        shutil.rmtree(tmpdir, ignore_errors=True)
        return None, None, response_error(500, "upload_failed", f"IO error: {str(io_error)}")
    except Exception as unexpected_error:
        logger.exception("Unexpected error during batch upload: %s", unexpected_error)
        shutil.rmtree(tmpdir, ignore_errors=True)
        return None, None, response_error(500, "upload_failed", str(unexpected_error))

    return saved_paths, tmpdir, None


def _active_transcribe_jobs_count() -> int:
    return sum(1 for job in JOBS.values() if isinstance(job, dict) and job.get("status") in ("queued", "running"))


def _queued_response(request: Request, job_id: str) -> JSONResponse:
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


def _default_enhance_params(enhance_mode: Optional[str], enhance_level: Optional[str], enhance: bool) -> tuple[str, str]:
    effective_mode = _resolve_enhance_mode(enhance_mode or settings.ENHANCE_MODE, enhance)
    effective_level = enhance_level or settings.ENHANCE_LEVEL
    return effective_mode, effective_level


async def _transcribe_common(
    request: Request,
    upload_files: List[UploadFile],
    async_mode: bool,
    model_name: Optional[str],
    enhance: bool,
    enhance_mode: Optional[str],
    enhance_level: Optional[str],
    whisper_mode: str,
    diarize: bool,
    punctuate: bool,
    auto_k: bool,
    max_speakers: int,
    enroll_threshold: float,
    device_sel: str,
    compute_sel: str,
    summary_mode: str,
    user_email: Optional[str],
):
    core = get_core()
    nlp_core.set_summary_source("local")
    is_batch = len(upload_files) > 1
    effective_enhance_mode, effective_enhance_level = _default_enhance_params(enhance_mode, enhance_level, enhance)

    if not is_batch:
        temp_file_path, upload_error = await _upload_file_to_temp(upload_files[0], settings.MAX_UPLOAD_MB)
        if upload_error:
            return upload_error

        if not async_mode:
            try:
                sync_job_id = str(uuid.uuid4())
                result = await asyncio.to_thread(
                    core.process,
                    str(temp_file_path),
                    model_name=model_name or settings.WHISPER_MODEL,
                    enhance=enhance,
                    enhance_mode=effective_enhance_mode,
                    enhance_level=effective_enhance_level,
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

        job_id = str(uuid.uuid4())
        max_queued = getattr(settings, "TRANSCRIBE_MAX_QUEUED", 20)
        if _active_transcribe_jobs_count() >= max_queued:
            return response_error(429, "rate_limited", f"too many queued or running transcribe jobs (max {max_queued})")

        JOBS[job_id] = {"status": "queued", "result_path": None, "error": None}
        job_kwargs = dict(
            model_name=model_name or settings.WHISPER_MODEL,
            enhance=enhance,
            enhance_mode=effective_enhance_mode,
            enhance_level=effective_enhance_level,
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
        return _queued_response(request, job_id)

    saved_files, tmpdir, upload_error = await _upload_files_to_temp(upload_files, settings.MAX_UPLOAD_MB)
    if upload_error:
        return upload_error

    cleanup_tmpdir = True
    try:
        saved_str = [str(path) for path in (saved_files or [])]
        if async_mode:
            job_id = str(uuid.uuid4())
            max_queued = getattr(settings, "TRANSCRIBE_MAX_QUEUED", 20)
            if _active_transcribe_jobs_count() >= max_queued:
                return response_error(429, "rate_limited", f"too many queued or running transcribe jobs (max {max_queued})")

            JOBS[job_id] = {"status": "queued", "result_path": None, "error": None}
            job_kwargs = dict(
                model_name=model_name or settings.WHISPER_MODEL,
                enhance=enhance,
                enhance_mode=effective_enhance_mode,
                enhance_level=effective_enhance_level,
                whisper_mode=whisper_mode,
                diarize=diarize,
                auto_k=auto_k,
                max_speakers=max_speakers,
                enroll_threshold=enroll_threshold,
                device_sel=device_sel,
                compute_sel=compute_sel,
                summary_mode=summary_mode,
                punctuate=punctuate,
                job_id=job_id,
            )
            cleanup_tmpdir = False
            asyncio.create_task(
                run_transcribe_batch_job_impl(
                    job_id,
                    [pathlib.Path(path) for path in saved_str],
                    job_kwargs,
                    get_core,
                )
            )
            if user_email:
                try:
                    DashboardService.record_activity(
                        user_email=user_email,
                        activity_type=ActivityType.ASR,
                        description="batch transcribe queued",
                        metadata={"mode": "async", "files_count": len(saved_str), "job_id": job_id},
                    )
                except Exception:
                    pass
            return _queued_response(request, job_id)

        batch_job_id = str(uuid.uuid4())
        result = await asyncio.to_thread(
            core.process_many,
            saved_str,
            model_name=model_name or settings.WHISPER_MODEL,
            enhance=enhance,
            enhance_mode=effective_enhance_mode,
            enhance_level=effective_enhance_level,
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
                    metadata={"files_count": len(saved_str)},
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
                s_text, kw_csv = nlp_core.summarize(merged_text, mode=summary_mode)
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
            except Exception as write_error:
                logger.warning("[WRITE_SUMMARY_BATCH] %s", write_error)
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
        if cleanup_tmpdir and tmpdir:
            try:
                shutil.rmtree(tmpdir)
            except Exception:
                pass


@router.post("/transcribe")
@router.post("/transcribe-batch")
@limiter.limit("6/minute")
async def transcribe(
    request: Request,
    file: Optional[UploadFile] = File(None),
    audio: UploadFile = File(None),
    files: Optional[List[UploadFile]] = File(None),
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
    upload_files = [uploaded for uploaded in (files or []) if uploaded is not None]
    if not upload_files:
        upload_file = file or audio
        if upload_file is not None:
            upload_files = [upload_file]
    if not upload_files:
        return response_error(400, "no_file", "use form field 'file' or 'audio' or 'files'")
    return await _transcribe_common(
        request=request,
        upload_files=upload_files,
        async_mode=async_mode,
        model_name=model_name,
        enhance=enhance,
        enhance_mode=enhance_mode,
        enhance_level=enhance_level,
        whisper_mode=whisper_mode,
        diarize=diarize,
        punctuate=punctuate,
        auto_k=auto_k,
        max_speakers=max_speakers,
        enroll_threshold=enroll_threshold,
        device_sel=device_sel,
        compute_sel=compute_sel,
        summary_mode=summary_mode,
        user_email=user_email,
    )
