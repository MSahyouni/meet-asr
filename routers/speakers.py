# routers/speakers.py
import pathlib
import secrets
import tempfile
from typing import List, Optional

from fastapi import APIRouter, File, Form, Header, UploadFile
from fastapi.responses import JSONResponse

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
    return {"files": core.get_speaker_files(name)}


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
