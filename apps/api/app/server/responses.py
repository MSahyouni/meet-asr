# server/responses.py — استجابات API موحّدة
import contextvars
from typing import Optional
from urllib.parse import quote
from fastapi.responses import JSONResponse

from ..config import settings
from .. import nlp_core

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("rid", default="")


def response_ok(
    text: str,
    summary: str,
    keywords: str,
    txt_path: Optional[str],
    summary_path: Optional[str],
    segments: Optional[list] = None,
    srt_path: Optional[str] = None,
    vtt_path: Optional[str] = None,
    segments_path: Optional[str] = None,
    job_id: Optional[str] = None,
    timings_ms: Optional[dict] = None,
) -> JSONResponse:
    base_url = settings.BASE_URL.rstrip("/")
    data = {
        "text": text or "",
        "summary": summary or "",
        "keywords": keywords or "",
        "request_id": request_id_var.get(),
        "job_id": job_id,
        "txt_path": txt_path,
        "summary_path": summary_path,
        "summary_source": nlp_core.get_summary_source(),
        "segments": segments or [],
        "srt_path": srt_path,
        "vtt_path": vtt_path,
        "segments_path": segments_path,
    }
    if timings_ms is not None:
        data["timings_ms"] = timings_ms
    if base_url and (txt_path or srt_path or vtt_path or summary_path or segments_path):
        def _u(p):
            return f"{base_url}/download?path={quote(p)}" if p else None
        data["download_urls"] = {
            "txt": _u(txt_path),
            "srt": _u(srt_path),
            "vtt": _u(vtt_path),
            "summary": _u(summary_path),
            "segments": _u(segments_path),
        }
    return JSONResponse(data)


def response_error(code: int, err: str, detail: Optional[str] = None) -> JSONResponse:
    payload = {
        "error": err,
        "detail": detail or "",
        "request_id": request_id_var.get(),
        "text": "",
        "summary": "",
        "keywords": "",
        "txt_path": None,
        "summary_path": None,
        "summary_source": nlp_core.get_summary_source(),
        "segments": [],
        "srt_path": None,
        "vtt_path": None,
        "segments_path": None,
        "download_urls": {"txt": None, "srt": None, "vtt": None, "summary": None},
    }
    return JSONResponse(payload, status_code=code)
