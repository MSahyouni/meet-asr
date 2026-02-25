# routers/tts.py — POST /tts (Kokoro TTS)
import asyncio
import pathlib
import uuid
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.features.dashboard.schema import ActivityType
from app.features.dashboard.service import DashboardService
from app.server.deps import response_error, limiter, check_api_key

router = APIRouter()


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


@router.post("/tts")
@limiter.limit("12/minute")
async def tts(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """
    Synthesize speech from text. Returns WAV path and download URL.
    Body (JSON): { "text", "voice" (optional), "speed" (optional), "seed" (optional, Arabic ar_mms rhythm), "format" (ignored; always wav) }
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
            core.synthesize, text=text or "", voice=voice, speed=speed, out_path=out_path, seed=seed
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
                metadata={"voice": voice, "job_id": job_id},
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
    })