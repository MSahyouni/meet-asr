# routers/export.py
import json
import pathlib
import secrets
from typing import Optional

from fastapi import APIRouter, Query, Header, Request
from fastapi.responses import FileResponse, JSONResponse, Response

from config import settings
from server.deps import get_core, response_error, parse_segments

router = APIRouter()


def _check_api_key(x_api_key: Optional[str]):
    if settings.API_TOKEN and not secrets.compare_digest(x_api_key or "", settings.API_TOKEN):
        return response_error(401, "unauthorized", "invalid api key")
    return None


@router.get("/download")
def download_txt(
    path: str = Query(..., description="Absolute or outputs-relative path to txt file"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    err = _check_api_key(x_api_key)
    if err:
        return err
    try:
        base = settings.OUTPUTS_DIR.resolve()
        p = pathlib.Path(path).expanduser()
        if not p.is_absolute():
            p = (base / p).resolve()
        else:
            p = p.resolve()
        if base not in p.parents and p.parent != base:
            return response_error(403, "forbidden_path", "outside outputs/")
        if not p.exists() or not p.is_file():
            return response_error(404, "file_not_found", p.as_posix())
        if p.suffix.lower() not in settings.DOWNLOAD_ALLOW:
            return response_error(403, "forbidden_extension", p.suffix.lower())
        media_types = {".wav": "audio/wav", ".mp3": "audio/mpeg"}
        media_type = media_types.get(p.suffix.lower(), "text/plain")
        return FileResponse(p.as_posix(), media_type=media_type, filename=p.name)
    except Exception as e:
        return response_error(500, "download_failed", str(e))


@router.get("/export.srt")
def export_srt(
    path: str = Query(..., description="Absolute or outputs-relative path to txt transcript"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    err = _check_api_key(x_api_key)
    if err:
        return err
    try:
        base = settings.OUTPUTS_DIR
        core = get_core()
        p = pathlib.Path(path).expanduser().resolve()
        if base not in p.parents and base != p.parent:
            return response_error(403, "forbidden_path", "outside outputs/")
        if not p.exists() or not p.is_file():
            return response_error(404, "file_not_found", p.as_posix())
        srt_ready = p.with_suffix(".srt")
        if srt_ready.exists():
            srt_path = srt_ready.as_posix()
        else:
            txt = p.read_text(encoding="utf-8", errors="ignore")
            segs = parse_segments(txt)
            srt_path = core.segments_to_srt(segs, p.as_posix())
        if not srt_path:
            return response_error(500, "srt_failed")
        return FileResponse(srt_path, media_type="application/x-subrip", filename=pathlib.Path(srt_path).name)
    except Exception as e:
        return response_error(500, "srt_failed", str(e))


@router.get("/export.vtt")
def export_vtt(
    path: str = Query(..., description="Absolute or outputs-relative path to txt transcript"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    err = _check_api_key(x_api_key)
    if err:
        return err
    try:
        base = settings.OUTPUTS_DIR
        core = get_core()
        p = pathlib.Path(path).expanduser().resolve()
        if base not in p.parents and base != p.parent:
            return response_error(403, "forbidden_path", "outside outputs/")
        if not p.exists() or not p.is_file():
            return response_error(404, "file_not_found", p.as_posix())
        vtt_ready = p.with_suffix(".vtt")
        if vtt_ready.exists():
            vtt_path = vtt_ready.as_posix()
        else:
            txt = p.read_text(encoding="utf-8", errors="ignore")
            segs = parse_segments(txt)
            vtt_path = core.segments_to_vtt(segs, p.as_posix())
        if not vtt_path:
            return response_error(500, "vtt_failed")
        return FileResponse(vtt_path, media_type="text/vtt", filename=pathlib.Path(vtt_path).name)
    except Exception as e:
        return response_error(500, "vtt_failed", str(e))


@router.get("/segments")
def segments_json_route(
    path: str = Query(..., description="Absolute or outputs-relative path to txt transcript"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    err = _check_api_key(x_api_key)
    if err:
        return err
    base = settings.OUTPUTS_DIR
    p = pathlib.Path(path).expanduser().resolve()
    if base not in p.parents and base != p.parent:
        return response_error(403, "forbidden_path", "outside outputs/")
    if not p.exists() or not p.is_file():
        return response_error(404, "file_not_found", p.as_posix())
    txt = p.read_text(encoding="utf-8", errors="ignore")
    return JSONResponse(parse_segments(txt))


@router.get("/segments/download")
def segments_download_route(
    path: str = Query(..., description="Absolute or outputs-relative path to txt transcript"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    err = _check_api_key(x_api_key)
    if err:
        return err
    base = settings.OUTPUTS_DIR
    p = pathlib.Path(path).expanduser().resolve()
    if base not in p.parents and base != p.parent:
        return response_error(403, "forbidden_path", "outside outputs/")
    if not p.exists() or not p.is_file():
        return response_error(404, "file_not_found", p.as_posix())
    txt = p.read_text(encoding="utf-8", errors="ignore")
    segs = parse_segments(txt)
    fname = p.with_suffix(".segments.json").name
    return Response(
        content=json.dumps(segs, ensure_ascii=False, indent=2),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
