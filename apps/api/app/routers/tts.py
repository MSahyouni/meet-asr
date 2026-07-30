# routers/tts.py — POST /tts (MMS / Habibi)
import asyncio
import json
import pathlib
from typing import List, Optional
from urllib.parse import quote

from app.storage.naming import new_timestamped_id

from fastapi import APIRouter, File, Form, Header, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from app.config import settings
from app.features.auth.deps import require_logged_in_user
from app.features.dashboard.schema import ActivityType
from app.features.dashboard.service import DashboardService
from app.server.deps import response_error, limiter, check_api_key
from app.storage.user_paths import is_under_outputs, user_tts_output_dir

router = APIRouter()

MAX_VOICE_SAMPLE_MB = 20


def _require_tts_auth(
    authorization: Optional[str],
    x_api_key: Optional[str],
    user_email: Optional[str] = None,
):
    auth_error = check_api_key(x_api_key)
    if auth_error:
        return None, auth_error
    return require_logged_in_user(user_email, authorization)


def _safe_under_outputs_tts(resolved: pathlib.Path) -> bool:
    """True if path is under outputs (global or per-user tts)."""
    try:
        return is_under_outputs(resolved.resolve())
    except Exception:
        return False


@router.get("/voices")
async def tts_voices(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Return TTS voice IDs plus per-engine readiness (does not load heavy models)."""
    _, auth_error = _require_tts_auth(authorization, x_api_key)
    if auth_error:
        return auth_error
    try:
        from app.tts_core import list_engine_status, list_voices, list_voices_detailed

        voices = list_voices()
        detailed = list_voices_detailed()
        engines = list_engine_status()
        return JSONResponse(
            {
                "ok": True,
                "voices": voices,
                "voices_detailed": detailed,
                "engines": engines,
            }
        )
    except Exception as e:
        return response_error(500, "voices_failed", str(e))


@router.post("/voice-sample")
@limiter.limit("20/minute")
async def upload_tts_voice_sample(
    request: Request,
    user_email: str = Form(...),
    ref_text: str = Form(""),
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Upload a speaker reference sample to user-specific folder: data/voices/<user>/"""
    resolved_email, auth_error = _require_tts_auth(authorization, x_api_key, user_email)
    if auth_error:
        return auth_error
    user_email = resolved_email
    try:
        from app.tts.voice_profiles import save_user_speaker_sample, save_user_speaker_ref_text, user_voice_dir

        raw = await file.read()
        if not raw:
            return response_error(400, "validation_error", "empty audio file")
        if len(raw) > MAX_VOICE_SAMPLE_MB * 1024 * 1024:
            return response_error(400, "validation_error", f"audio sample too large (max {MAX_VOICE_SAMPLE_MB}MB)")

        saved = save_user_speaker_sample(user_email=user_email, content=raw, filename=file.filename or "voice.wav")
        ref_text_value = (ref_text or "").strip()
        if ref_text_value:
            save_user_speaker_ref_text(user_email=user_email, speaker_ref=saved.name, ref_text=ref_text_value)
        directory = user_voice_dir(user_email)
        return JSONResponse(
            {
                "ok": True,
                "user_email": user_email,
                "speaker_ref": saved.name,
                "has_ref_text": bool(ref_text_value),
                "voice_dir": directory.as_posix(),
                "bytes": len(raw),
                "message": "voice sample uploaded",
            }
        )
    except ValueError as e:
        return response_error(400, "validation_error", str(e))
    except Exception as e:
        return response_error(500, "upload_failed", str(e))


@router.post("/voice-samples")
@limiter.limit("20/minute")
async def upload_tts_voice_samples(
    request: Request,
    user_email: str = Form(...),
    ref_texts_json: str = Form(""),
    default_ref_text: str = Form(""),
    files: List[UploadFile] = File(...),
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Upload multiple speaker samples to user-specific folder: data/voices/<user>/"""
    resolved_email, auth_error = _require_tts_auth(authorization, x_api_key, user_email)
    if auth_error:
        return auth_error
    user_email = resolved_email
    try:
        from app.tts.voice_profiles import save_user_speaker_ref_text, save_user_speaker_sample, user_voice_dir

        ref_text_map = {}
        if (ref_texts_json or "").strip():
            try:
                parsed = json.loads(ref_texts_json)
            except Exception as e:
                return response_error(400, "validation_error", f"invalid ref_texts_json: {e}")
            if not isinstance(parsed, dict):
                return response_error(400, "validation_error", "ref_texts_json must be a JSON object")
            for key, value in parsed.items():
                key_norm = pathlib.Path(str(key)).name
                value_norm = (str(value) if value is not None else "").strip()
                if key_norm and value_norm:
                    ref_text_map[key_norm] = value_norm

        default_ref_text_value = (default_ref_text or "").strip()

        saved_files = []
        saved_file_details = []
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

            candidate_keys = [
                pathlib.Path(uploaded.filename or "").name,
                saved.name,
            ]
            ref_text_value = ""
            for key in candidate_keys:
                if key in ref_text_map:
                    ref_text_value = ref_text_map[key]
                    break
            if not ref_text_value:
                ref_text_value = default_ref_text_value
            if ref_text_value:
                save_user_speaker_ref_text(user_email=user_email, speaker_ref=saved.name, ref_text=ref_text_value)

            saved_files.append(saved.name)
            saved_file_details.append(
                {
                    "name": saved.name,
                    "bytes": len(raw),
                    "has_ref_text": bool(ref_text_value),
                }
            )
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
                "file_details": saved_file_details,
                "count": len(saved_files),
                "bytes": total_bytes,
                "message": "voice samples uploaded",
            }
        )
    except ValueError as e:
        return response_error(400, "validation_error", str(e))
    except Exception as e:
        return response_error(500, "upload_failed", str(e))


@router.get("/voice-samples")
def list_tts_voice_samples(
    user_email: str = Query(...),
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """List uploaded speaker sample files for a specific user folder."""
    resolved_email, auth_error = _require_tts_auth(authorization, x_api_key, user_email)
    if auth_error:
        return auth_error
    user_email = resolved_email
    try:
        from app.tts.voice_profiles import get_user_speaker_ref_text, list_user_speaker_samples, user_voice_dir

        files = list_user_speaker_samples(user_email)
        directory = user_voice_dir(user_email)
        file_items = []
        for f in files:
            ref_text_value = get_user_speaker_ref_text(user_email, f.name)
            file_items.append(
                {
                    "name": f.name,
                    "size_bytes": f.stat().st_size,
                    "has_ref_text": bool(ref_text_value),
                    "ref_text": ref_text_value,
                }
            )
        return JSONResponse(
            {
                "ok": True,
                "user_email": user_email,
                "voice_dir": directory.as_posix(),
                "files": file_items,
            }
        )
    except ValueError as e:
        return response_error(400, "validation_error", str(e))
    except Exception as e:
        return response_error(500, "list_failed", str(e))


@router.get("/voice-file")
def get_tts_voice_file(
    user_email: str = Query(...),
    file: str = Query(..., description="Voice sample file name (basename only)"),
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Stream one user speaker sample for preview/playback."""
    resolved_email, auth_error = _require_tts_auth(authorization, x_api_key, user_email)
    if auth_error:
        return auth_error
    user_email = resolved_email
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


@router.delete("/voice-sample")
def delete_tts_voice_sample(
    user_email: str = Query(...),
    file: str = Query(...),
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Delete one speaker sample file from user-specific voice folder."""
    resolved_email, auth_error = _require_tts_auth(authorization, x_api_key, user_email)
    if auth_error:
        return auth_error
    user_email = resolved_email
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


@router.post("/suggest-dialect")
@limiter.limit("60/minute")
async def tts_suggest_dialect(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Suggest Habibi dialect from generation text. Body: { text, current? }."""
    _, auth_error = _require_tts_auth(authorization, x_api_key)
    if auth_error:
        return auth_error
    try:
        body = await request.json()
    except Exception as json_error:
        return response_error(400, "invalid_json", str(json_error))
    if not isinstance(body, dict):
        return response_error(400, "invalid_body", "JSON object required")
    from app.tts.dialect_suggest import suggest_habibi_dialect

    result = suggest_habibi_dialect(
        text=(body.get("text") or ""),
        current=(body.get("current") or body.get("dialect") or "UNK"),
    )
    return JSONResponse({"ok": True, **result})


@router.post("/voice-sample/inspect")
@limiter.limit("30/minute")
async def tts_inspect_voice_sample(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Inspect duration/silence/ref_text readiness for a user voice sample."""
    try:
        body = await request.json()
    except Exception as json_error:
        return response_error(400, "invalid_json", str(json_error))
    if not isinstance(body, dict):
        return response_error(400, "invalid_body", "JSON object required")

    user_email = (body.get("user_email") or "").strip() or None
    resolved_email, auth_error = _require_tts_auth(authorization, x_api_key, user_email)
    if auth_error:
        return auth_error
    user_email = resolved_email
    speaker_ref = (body.get("speaker_ref") or body.get("file") or "").strip()
    if not speaker_ref:
        return response_error(400, "validation_error", "speaker_ref is required")
    form_ref_text = (body.get("ref_text") or "").strip() or None

    try:
        from app.tts.voice_profiles import get_user_speaker_ref_text, resolve_user_speaker_path
        from app.tts.voice_sample_check import inspect_voice_sample

        path = resolve_user_speaker_path(user_email=user_email, speaker_ref=speaker_ref)
        if not path.exists() or not path.is_file():
            return response_error(404, "not_found", "voice sample not found")
        saved_ref = get_user_speaker_ref_text(user_email, path.name)
        info = inspect_voice_sample(
            str(path),
            has_ref_text=bool(saved_ref),
            ref_text=form_ref_text or saved_ref,
        )
        info["user_email"] = user_email
        info["speaker_ref"] = path.name
        info["saved_ref_text"] = saved_ref
        return JSONResponse(info)
    except ValueError as e:
        return response_error(400, "validation_error", str(e))
    except Exception as e:
        return response_error(500, "inspect_failed", str(e))


@router.post("/voice-sample/transcribe-ref")
@limiter.limit("8/minute")
async def tts_transcribe_voice_ref(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """
    Transcribe a short voice sample with Whisper and optionally save as ref_text.
    Body: { user_email, speaker_ref, save?=true }
    """
    try:
        body = await request.json()
    except Exception as json_error:
        return response_error(400, "invalid_json", str(json_error))
    if not isinstance(body, dict):
        return response_error(400, "invalid_body", "JSON object required")

    user_email = (body.get("user_email") or "").strip() or None
    resolved_email, auth_error = _require_tts_auth(authorization, x_api_key, user_email)
    if auth_error:
        return auth_error
    user_email = resolved_email
    speaker_ref = (body.get("speaker_ref") or body.get("file") or "").strip()
    if not speaker_ref:
        return response_error(400, "validation_error", "speaker_ref is required")
    save = body.get("save", True)
    if isinstance(save, str):
        save = save.strip().lower() in ("1", "true", "yes", "on")

    try:
        from app.asr.whisper import get_model, run_asr
        from app.config import settings
        from app.tts.text_utils import strip_arabic_diacritics
        from app.tts.voice_profiles import (
            resolve_user_speaker_path,
            save_user_speaker_ref_text,
        )
        from app.tts.voice_sample_check import inspect_voice_sample

        path = resolve_user_speaker_path(user_email=user_email, speaker_ref=speaker_ref)
        if not path.exists() or not path.is_file():
            return response_error(404, "not_found", "voice sample not found")

        inspect = inspect_voice_sample(str(path), has_ref_text=True)
        if inspect.get("duration_sec", 0) > 30:
            return response_error(
                400,
                "validation_error",
                "العينة أطول من 30 ثانية — قصّها إلى 5–10 ثوانٍ قبل استخراج ref_text",
            )

        model_name = (getattr(settings, "WHISPER_MODEL", None) or "small").strip() or "small"
        # Prefer a lighter alias if project uses "heavy"/"normal" names via resolve_model.
        model = get_model(model_name, device=getattr(settings, "WHISPER_DEVICE", None), compute_type=getattr(settings, "WHISPER_COMPUTE", None))
        _meta, segments = await asyncio.to_thread(run_asr, str(path), model, "normal", False)
        ref_text = " ".join((s.get("text") or "").strip() for s in (segments or []) if (s.get("text") or "").strip())
        ref_text = strip_arabic_diacritics(ref_text)
        ref_text = " ".join(ref_text.split()).strip()
        if not ref_text:
            return response_error(422, "empty_transcript", "لم يُستخرج نص من البصمة — جرّب عينة أوضح")

        saved = False
        if save:
            save_user_speaker_ref_text(user_email=user_email, speaker_ref=path.name, ref_text=ref_text)
            saved = True

        return JSONResponse(
            {
                "ok": True,
                "user_email": user_email,
                "speaker_ref": path.name,
                "ref_text": ref_text,
                "saved": saved,
                "duration_sec": inspect.get("duration_sec"),
                "warnings": [w for w in (inspect.get("warnings") or []) if w.get("code") != "missing_ref_text"],
            }
        )
    except ValueError as e:
        return response_error(400, "validation_error", str(e))
    except Exception as e:
        return response_error(500, "transcribe_ref_failed", str(e))


@router.post("")
@router.post("/", include_in_schema=False)
@limiter.limit("12/minute")
async def tts(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """
    Synthesize speech from text. Returns WAV path and download URL.
    Body (JSON): { "text", "voice" (optional; alias voice_id), "speed" (optional), "seed" (optional), "engine" (auto|mms|habibi|omnivoice), "speaker_ref" (optional), "ref_text" (required for habibi), "dialect" (optional for habibi), "diacritize" (optional bool; overrides TTS_DIACRITIZE), "format" (ignored; always wav) }
    Max text length: 5000 chars. Rate: 12/minute per IP.
    download_url uses /download (legacy /asr/download still accepted).
    """
    try:
        body = await request.json()
    except Exception as json_error:
        return response_error(400, "invalid_json", str(json_error))
    if not isinstance(body, dict):
        return response_error(400, "invalid_body", "JSON object required")

    user_email = (body.get("user_email") or "").strip() or None
    resolved_email, auth_error = _require_tts_auth(authorization, x_api_key, user_email)
    if auth_error:
        return auth_error
    user_email = resolved_email

    text = (body.get("text") or "").strip()
    if not text:
        return response_error(400, "validation_error", "text is required and cannot be empty")
    from app.tts_core import TTS_TEXT_MAX_LEN
    if len(text) > TTS_TEXT_MAX_LEN:
        return response_error(400, "validation_error", f"text length exceeds maximum ({TTS_TEXT_MAX_LEN} characters)")
    engine = (body.get("engine") or "auto").strip().lower() or "auto"
    # Accept voice_id as Flutter/legacy alias for voice.
    voice = (body.get("voice") or body.get("voice_id") or "").strip()
    if not voice:
        # Align defaults with engine: auto prefers clone-capable voice id; mms → ar_mms.
        voice = "ar_mms" if engine == "mms" else "omnivoice"
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
    speaker_ref = (body.get("speaker_ref") or "").strip() or None
    ref_text = (body.get("ref_text") or "").strip() or None
    dialect = (body.get("dialect") or "").strip() or None

    diacritize = None
    if "diacritize" in body:
        raw_d = body.get("diacritize")
        if isinstance(raw_d, bool):
            diacritize = raw_d
        elif isinstance(raw_d, (int, float)):
            diacritize = bool(raw_d)
        elif raw_d is None:
            diacritize = None
        else:
            s = str(raw_d).strip().lower()
            if s in ("1", "true", "yes", "on"):
                diacritize = True
            elif s in ("0", "false", "no", "off"):
                diacritize = False

    max_chunk_chars = None
    raw_chunk = body.get("max_chunk_chars", body.get("habibi_max_chunk"))
    if raw_chunk is not None and str(raw_chunk).strip() != "":
        try:
            max_chunk_chars = max(48, min(220, int(raw_chunk)))
        except (TypeError, ValueError):
            max_chunk_chars = None

    # format is accepted but we only output wav

    # Generate unique path under per-user or global tts output dir.
    tts_dir = user_tts_output_dir(user_email)
    job_id = new_timestamped_id("tts")
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
            ref_text=ref_text,
            dialect=dialect,
            diacritize=diacritize,
            max_chunk_chars=max_chunk_chars,
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
    if not _safe_under_outputs_tts(resolved):
        return response_error(403, "forbidden_path", "outside outputs/")
    if resolved.suffix.lower() not in settings.DOWNLOAD_ALLOW:
        return response_error(403, "forbidden_extension", resolved.suffix.lower())

    # Neutral download path (legacy /asr/download still works).
    download_url = f"/download?path={quote(resolved.as_posix())}"

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
                    "dialect": result.get("dialect"),
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
        "engine_used": result.get("engine_used", "mms_arabic"),
        "arabic_detected": bool(result.get("arabic_detected", False)),
        "fallback_used": bool(result.get("fallback_used", False)),
        "requested_voice": result.get("requested_voice", voice),
        "resolved_voice": result.get("resolved_voice", result.get("voice", voice)),
        "speaker_ref": result.get("speaker_ref"),
        "dialect": result.get("dialect"),
        "diacritize": bool(result.get("diacritize", False)),
        "max_chunk_chars": result.get("max_chunk_chars"),
    })