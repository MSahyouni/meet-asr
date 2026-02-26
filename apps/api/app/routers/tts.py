# routers/tts.py — POST /tts (Kokoro TTS)
import asyncio
import pathlib
import uuid
from typing import List, Optional
from urllib.parse import quote

from fastapi import APIRouter, File, Form, Header, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from app.config import settings
from app.features.dashboard.schema import ActivityType
from app.features.dashboard.service import DashboardService
from app.server.deps import response_error, limiter, check_api_key

router = APIRouter()

MAX_VOICE_SAMPLE_MB = 20


def _safe_under_outputs_tts(resolved: pathlib.Path) -> bool:
    """True if path is under settings.OUTPUTS_DIR/tts (no path traversal)."""
    base = (settings.OUTPUTS_DIR / "tts").resolve()
    try:
        resolved = resolved.resolve()
        return base in resolved.parents or resolved.parent == base
    except Exception:
        return False


@router.get("/tts/voices")
async def tts_voices(x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Return list of available TTS voice IDs. Does not load the TTS model."""
    auth_error = check_api_key(x_api_key)
    if auth_error:
        return auth_error
    try:
        from app.tts_core import list_voices
        voices = list_voices()
        return JSONResponse({"ok": True, "voices": voices})
    except Exception as e:
        return response_error(500, "voices_failed", str(e))


@router.post("/tts/voice-sample")
@limiter.limit("20/minute")
async def upload_tts_voice_sample(
    request: Request,
    user_email: str = Form(...),
    file: UploadFile = File(...),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Upload a speaker reference sample to user-specific folder: data/voices/<user>/"""
    auth_error = check_api_key(x_api_key)
    if auth_error:
        return auth_error
    try:
        from app.tts.voice_profiles import save_user_speaker_sample, user_voice_dir

        raw = await file.read()
        if not raw:
            return response_error(400, "validation_error", "empty audio file")
        if len(raw) > MAX_VOICE_SAMPLE_MB * 1024 * 1024:
            return response_error(400, "validation_error", f"audio sample too large (max {MAX_VOICE_SAMPLE_MB}MB)")

        saved = save_user_speaker_sample(user_email=user_email, content=raw, filename=file.filename or "voice.wav")
        directory = user_voice_dir(user_email)
        return JSONResponse(
            {
                "ok": True,
                "user_email": user_email,
                "speaker_ref": saved.name,
                "voice_dir": directory.as_posix(),
                "bytes": len(raw),
                "message": "voice sample uploaded",
            }
        )
    except ValueError as e:
        return response_error(400, "validation_error", str(e))
    except Exception as e:
        return response_error(500, "upload_failed", str(e))


@router.post("/tts/voice-samples")
@limiter.limit("20/minute")
async def upload_tts_voice_samples(
    request: Request,
    user_email: str = Form(...),
    files: List[UploadFile] = File(...),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Upload multiple speaker samples to user-specific folder: data/voices/<user>/"""
    auth_error = check_api_key(x_api_key)
    if auth_error:
        return auth_error
    try:
        from app.tts.voice_profiles import save_user_speaker_sample, user_voice_dir

        saved_files = []
        total_bytes = 0
        for uploaded in files:
            raw = await uploaded.read()
            if not raw:
                continue
            if len(raw) > MAX_VOICE_SAMPLE_MB * 1024 * 1024:
                return response_error(
                    400,
                    "validation_error",
                    f"audio sample too large: {uploaded.filename} (max {MAX_VOICE_SAMPLE_MB}MB)",
                )
            saved = save_user_speaker_sample(
                user_email=user_email,
                content=raw,
                filename=(uploaded.filename or "voice.wav"),
            )
            saved_files.append(saved.name)
            total_bytes += len(raw)

        if not saved_files:
            return response_error(400, "validation_error", "no valid audio files uploaded")

        directory = user_voice_dir(user_email)
        return JSONResponse(
            {
                "ok": True,
                "user_email": user_email,
                "voice_dir": directory.as_posix(),
                "files": saved_files,
                "count": len(saved_files),
                "bytes": total_bytes,
                "message": "voice samples uploaded",
            }
        )
    except ValueError as e:
        return response_error(400, "validation_error", str(e))
    except Exception as e:
        return response_error(500, "upload_failed", str(e))


@router.get("/tts/voice-samples")
def list_tts_voice_samples(
    user_email: str = Query(...),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """List uploaded speaker sample files for a specific user folder."""
    auth_error = check_api_key(x_api_key)
    if auth_error:
        return auth_error
    try:
        from app.tts.voice_profiles import list_user_speaker_samples, user_voice_dir

        files = list_user_speaker_samples(user_email)
        directory = user_voice_dir(user_email)
        return JSONResponse(
            {
                "ok": True,
                "user_email": user_email,
                "voice_dir": directory.as_posix(),
                "files": [
                    {
                        "name": f.name,
                        "size_bytes": f.stat().st_size,
                    }
                    for f in files
                ],
            }
        )
    except ValueError as e:
        return response_error(400, "validation_error", str(e))
    except Exception as e:
        return response_error(500, "list_failed", str(e))


@router.get("/tts/voice-file")
def get_tts_voice_file(
    user_email: str = Query(...),
    file: str = Query(..., description="Voice sample file name (basename only)"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Stream one user speaker sample for preview/playback."""
    auth_error = check_api_key(x_api_key)
    if auth_error:
        return auth_error
    try:
        from app.tts.voice_profiles import resolve_user_speaker_path

        target = resolve_user_speaker_path(user_email=user_email, speaker_ref=file)
        if not target.exists() or not target.is_file():
            return response_error(404, "not_found", "voice sample not found")
        media_types = {
            ".wav": "audio/wav",
            ".mp3": "audio/mpeg",
            ".m4a": "audio/mp4",
            ".ogg": "audio/ogg",
            ".flac": "audio/flac",
            ".aac": "audio/aac",
            ".opus": "audio/ogg",
        }
        media_type = media_types.get(target.suffix.lower(), "application/octet-stream")
        return FileResponse(str(target), media_type=media_type, filename=target.name)
    except ValueError as e:
        return response_error(400, "validation_error", str(e))
    except Exception as e:
        return response_error(500, "download_failed", str(e))


@router.delete("/tts/voice-sample")
def delete_tts_voice_sample(
    user_email: str = Query(...),
    file: str = Query(...),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Delete one speaker sample file from user-specific voice folder."""
    auth_error = check_api_key(x_api_key)
    if auth_error:
        return auth_error
    try:
        from app.tts.voice_profiles import delete_user_speaker_sample

        ok = delete_user_speaker_sample(user_email=user_email, speaker_ref=file)
        if not ok:
            return response_error(404, "not_found", "voice sample not found")
        return JSONResponse({"ok": True, "user_email": user_email, "deleted": file})
    except ValueError as e:
        return response_error(400, "validation_error", str(e))
    except Exception as e:
        return response_error(500, "delete_failed", str(e))


@router.post("/tts")
@limiter.limit("12/minute")
async def tts(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """
    Synthesize speech from text. Returns WAV path and download URL.
    Body (JSON): { "text", "voice" (optional), "speed" (optional), "seed" (optional), "engine" (auto|mms|kokoro|xtts), "speaker_ref" (optional for xtts), "format" (ignored; always wav) }
    Max text length: 5000 chars. Rate: 12/minute per IP.
    """
    auth_error = check_api_key(x_api_key)
    if auth_error:
        return auth_error
    try:
        body = await request.json()
    except Exception as json_error:
        return response_error(400, "invalid_json", str(json_error))
    if not isinstance(body, dict):
        return response_error(400, "invalid_body", "JSON object required")
    text = (body.get("text") or "").strip()
    user_email = (body.get("user_email") or "").strip() or None
    if not text:
        return response_error(400, "validation_error", "text is required and cannot be empty")
    from app.tts_core import TTS_TEXT_MAX_LEN
    if len(text) > TTS_TEXT_MAX_LEN:
        return response_error(400, "validation_error", f"text length exceeds maximum ({TTS_TEXT_MAX_LEN} characters)")
    voice = (body.get("voice") or "af_heart").strip() or "af_heart"
    try:
        speed = float(body.get("speed", 1.0))
    except (TypeError, ValueError):
        speed = 1.0
    seed = body.get("seed")
    if seed is not None:
        try:
            seed = int(seed)
        except (TypeError, ValueError):
            seed = None
    engine = (body.get("engine") or "auto").strip().lower() or "auto"
    speaker_ref = (body.get("speaker_ref") or "").strip() or None
    # format is accepted but we only output wav

    # Generate unique path under outputs/tts/ (no user-controlled path → no path traversal)
    tts_dir = pathlib.Path(settings.OUTPUTS_DIR) / "tts"
    tts_dir.mkdir(parents=True, exist_ok=True)
    job_id = str(uuid.uuid4())
    out_path = str((tts_dir / f"{job_id}.wav").resolve())
    if not _safe_under_outputs_tts(pathlib.Path(out_path)):
        return response_error(403, "forbidden_path", "path outside outputs/tts/")

    try:
        from app.tts_core import get_tts_core
        core = get_tts_core()
        result = await asyncio.to_thread(
            core.synthesize,
            text=text or "",
            voice=voice,
            speed=speed,
            out_path=out_path,
            seed=seed,
            engine=engine,
            user_email=user_email,
            speaker_ref=speaker_ref,
        )
    except ValueError as e:
        return response_error(400, "validation_error", str(e))
    except RuntimeError as e:
        return response_error(500, "tts_failed", str(e))
    except Exception as e:
        return response_error(500, "tts_failed", str(e))

    # Same path whitelist as /download: path must be under OUTPUTS_DIR
    audio_path = result["audio_path"]
    resolved = pathlib.Path(audio_path).resolve()
    base_out = settings.OUTPUTS_DIR.resolve()
    if base_out not in resolved.parents and resolved.parent != base_out:
        return response_error(403, "forbidden_path", "outside outputs/")
    if resolved.suffix.lower() not in settings.DOWNLOAD_ALLOW:
        return response_error(403, "forbidden_extension", resolved.suffix.lower())

    base_url = settings.BASE_URL.rstrip("/") or str(request.base_url).rstrip("/")
    download_url = f"/download?path={quote(resolved.as_posix())}"
    if base_url:
        download_url = f"{base_url}{download_url}"

    if user_email:
        try:
            DashboardService.record_activity(
                user_email=user_email,
                activity_type=ActivityType.TTS,
                description="tts completed",
                metadata={
                    "voice": voice,
                    "job_id": job_id,
                    "engine_used": result.get("engine_used"),
                    "fallback_used": bool(result.get("fallback_used", False)),
                    "resolved_voice": result.get("resolved_voice"),
                    "speaker_ref": result.get("speaker_ref"),
                },
            )
        except Exception:
            pass

    return JSONResponse({
        "ok": True,
        "job_id": job_id,
        "audio_path": audio_path,
        "download_url": download_url,
        "duration_sec": result["duration_sec"],
        "sample_rate": result["sample_rate"],
        "engine_used": result.get("engine_used", "kokoro"),
        "arabic_detected": bool(result.get("arabic_detected", False)),
        "fallback_used": bool(result.get("fallback_used", False)),
        "requested_voice": result.get("requested_voice", voice),
        "resolved_voice": result.get("resolved_voice", result.get("voice", voice)),
        "speaker_ref": result.get("speaker_ref"),
    })