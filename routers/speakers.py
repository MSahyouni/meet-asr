# routers/speakers.py
import pathlib
import secrets
import tempfile
from typing import List, Optional

from fastapi import APIRouter, File, Form, Header, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse

import aiofiles
from config import settings
from server.deps import get_core, response_error

router = APIRouter()


def _check_api_key(x_api_key: Optional[str]) -> Optional[JSONResponse]:
    if settings.API_TOKEN and not secrets.compare_digest(x_api_key or "", settings.API_TOKEN):
        return response_error(401, "unauthorized", "invalid api key")
    return None


@router.delete("/delete-speaker")
def delete_speaker_route(
    name: str,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    err = _check_api_key(x_api_key)
    if err:
        return err
    core = get_core()
    ok, msg = core.delete_speaker(name)
    return {"success": bool(ok), "message": msg}


@router.get("/speaker-files")
def speaker_files_route(
    name: str,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    err = _check_api_key(x_api_key)
    if err:
        return err
    core = get_core()
    full_paths = core.get_speaker_files(name)
    # Return file names only so frontend can request via /speaker-file?name=&file=
    names = [pathlib.Path(p).name for p in full_paths]
    return {"files": names}


@router.get("/speaker-file")
def speaker_file_route(
    name: str = Query(...),
    file: str = Query(..., description="File name (basename only)"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Stream a speaker enrollment file for playback (e.g. audio in browser)."""
    err = _check_api_key(x_api_key)
    if err:
        return err
    name = (name or "").strip()
    file = (file or "").strip()
    if not name or not file:
        return response_error(400, "missing_params", "name and file required")
    # No path traversal: file must be a single path component
    if "/" in file or "\\" in file or pathlib.Path(file).name != file:
        return response_error(403, "forbidden", "invalid file name")
    base = (settings.SPK_DIR / name).resolve()
    try:
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
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    err = _check_api_key(x_api_key)
    if err:
        return err
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
            saved_files.append(str(dst))
        success, message = core.enroll_voice(name, saved_files)
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
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    err = _check_api_key(x_api_key)
    if err:
        return err
    try:
        core = get_core()
        speakers = core.load_enrolled()
        return {"speakers": speakers}
    except Exception as e:
        return response_error(500, "failed_to_load_speakers", str(e))
