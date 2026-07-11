# routers/speakers.py
import pathlib
import subprocess
import tempfile
from typing import List, Optional

from fastapi import APIRouter, File, Form, Header, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse

import aiofiles
from app.config import settings
from app.server.deps import get_core, response_error, check_api_key
from app.features.auth.deps import require_logged_in_user
from app.storage.user_paths import speaker_enrollment_dir

router = APIRouter()


def _ffmpeg_convert_to_wav(src: pathlib.Path, dst: pathlib.Path) -> tuple[bool, str]:
    """Convert audio to 16kHz mono WAV using ffmpeg."""
    try:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(src),
                "-ac",
                "1",
                "-ar",
                "16000",
                "-f",
                "wav",
                str(dst),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if proc.returncode != 0:
            err = (proc.stderr or b"").decode("utf-8", errors="ignore").strip()
            return False, err or "ffmpeg failed"
        if not dst.exists() or dst.stat().st_size == 0:
            return False, "ffmpeg produced empty output"
        return True, ""
    except FileNotFoundError:
        return False, "ffmpeg not found"
    except Exception as e:
        return False, str(e)


@router.delete("/delete-speaker")
def delete_speaker_route(
    name: str,
    user_email: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    auth_error = check_api_key(x_api_key)
    if auth_error:
        return auth_error
    resolved_email, login_error = require_logged_in_user(user_email, authorization)
    if login_error:
        return login_error
    core = get_core()
    ok, msg = core.delete_speaker(name, user_email=resolved_email)
    return {"success": bool(ok), "message": msg}


@router.get("/speaker-files")
def speaker_files_route(
    name: str,
    user_email: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    auth_error = check_api_key(x_api_key)
    if auth_error:
        return auth_error
    resolved_email, login_error = require_logged_in_user(user_email, authorization)
    if login_error:
        return login_error
    core = get_core()
    full_paths = core.get_speaker_files(name, user_email=resolved_email)
    names = [pathlib.Path(p).name for p in full_paths]
    return {"files": names}


@router.get("/speaker-file")
def speaker_file_route(
    name: str = Query(...),
    file: str = Query(..., description="File name (basename only)"),
    user_email: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    auth_error = check_api_key(x_api_key)
    if auth_error:
        return auth_error
    resolved_email, login_error = require_logged_in_user(user_email, authorization)
    if login_error:
        return login_error
    name = (name or "").strip()
    file = (file or "").strip()
    if not name or not file:
        return response_error(400, "missing_params", "name and file required")
    if "/" in file or "\\" in file or pathlib.Path(file).name != file:
        return response_error(403, "forbidden", "invalid file name")
    try:
        base = speaker_enrollment_dir(resolved_email, name)
        target = (base / file).resolve()
        if not base.exists() or not target.exists() or not target.is_file():
            return response_error(404, "not_found", "file not found")
        if base not in target.parents and target.parent != base:
            return response_error(403, "forbidden", "outside speaker dir")
        if target.suffix.lower() not in settings.ALLOWED_EXT:
            return response_error(403, "forbidden_extension", target.suffix.lower())
        media_types = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".ogg": "audio/ogg"}
        media_type = media_types.get(target.suffix.lower(), "application/octet-stream")
        return FileResponse(str(target), media_type=media_type, filename=target.name)
    except Exception as e:
        return response_error(500, "download_failed", str(e))


@router.post("/enroll-speaker")
async def enroll_speaker_route(
    name: str = Form(...),
    files: List[UploadFile] = File(...),
    user_email: Optional[str] = Form(None),
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    auth_error = check_api_key(x_api_key)
    if auth_error:
        return auth_error
    resolved_email, login_error = require_logged_in_user(user_email, authorization)
    if login_error:
        return login_error
    core = get_core()
    tmpdir = tempfile.mkdtemp(prefix="enroll_")
    try:
        saved_files: List[str] = []
        for uf in files:
            dst = pathlib.Path(tmpdir) / (uf.filename or f"voice_{len(saved_files)}.wav")
            async with aiofiles.open(dst, "wb") as f:
                content = await uf.read()
                await f.write(content)
            try:
                if dst.stat().st_size > settings.MAX_UPLOAD_MB * 1024 * 1024:
                    return response_error(413, "file_too_large", f"max={settings.MAX_UPLOAD_MB}MB")
            except Exception:
                pass
            if dst.suffix.lower() not in settings.ALLOWED_EXT:
                return response_error(415, "unsupported_media_type", dst.suffix.lower())

            if dst.suffix.lower() != ".wav":
                wav_dst = dst.with_suffix(".wav")
                ok, err = _ffmpeg_convert_to_wav(dst, wav_dst)
                if not ok:
                    return response_error(
                        400,
                        "audio_decode_failed",
                        f"failed to decode {dst.suffix.lower()} (ffmpeg): {err}",
                    )
                saved_files.append(str(wav_dst))
            else:
                saved_files.append(str(dst))
        success, message = core.enroll_voice(name, saved_files, user_email=resolved_email)
        return JSONResponse({"success": bool(success), "message": message or ""})
    except Exception as e:
        return response_error(500, "enrollment_failed", str(e))
    finally:
        import shutil
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass


@router.get("/enrolled-speakers")
def get_enrolled_speakers_route(
    user_email: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    auth_error = check_api_key(x_api_key)
    if auth_error:
        return auth_error
    resolved_email, login_error = require_logged_in_user(user_email, authorization)
    if login_error:
        return login_error
    try:
        core = get_core()
        speakers = core.load_enrolled(user_email=resolved_email)
        return {"speakers": speakers}
    except Exception as e:
        return response_error(500, "failed_to_load_speakers", str(e))
