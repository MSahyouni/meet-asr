# routers/summarize.py
import pathlib
import secrets
import asyncio
from typing import Optional

from fastapi import APIRouter, Form, File, Header, Request, UploadFile
from fastapi.responses import JSONResponse

import nlp_core
from config import settings
from server.deps import response_error, JOBS, run_summary_job_impl, limiter

router = APIRouter()


def _check_api_key(x_api_key: Optional[str]) -> Optional[JSONResponse]:
    if settings.API_TOKEN and not secrets.compare_digest(x_api_key or "", settings.API_TOKEN):
        return response_error(401, "unauthorized", "invalid api key")
    return None


@router.post("/summarize")
@limiter.limit("12/minute")
async def summarize_after(
    request: Request,
    text: Optional[str] = Form(None),
    path: Optional[str] = Form(None),
    summary_mode: str = Form("lite"),
    async_mode: bool = Form(False),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    fake_file: Optional[UploadFile] = File(None),
):
    err = _check_api_key(x_api_key)
    if err:
        return err

    body = (text or "").strip()
    if (path or "").strip():
        try:
            p = pathlib.Path(path).expanduser().resolve()
            base = settings.OUTPUTS_DIR
            if base not in p.parents and base != p.parent:
                return response_error(403, "forbidden_path", "outside outputs/")
            if not p.exists() or not p.is_file():
                return response_error(404, "file_not_found", p.as_posix())
            body = p.read_text(encoding="utf-8", errors="ignore")
            out_base_path = p
        except Exception as e:
            return response_error(500, "read_failed", str(e))
    else:
        out_base_path = settings.OUTPUTS_DIR / "manual_summary"

    if not body:
        return response_error(400, "no_text", "nothing to summarize")

    if not async_mode:
        s_text, kw_csv = nlp_core.summarize(body, mode=summary_mode)
        if not s_text.strip():
            nlp_core.set_summary_source("off")
            return JSONResponse({"summary": "", "keywords": "", "summary_path": None, "summary_source": "off"})
        try:
            sum_path = str(out_base_path.with_suffix(".summary.txt"))
            pathlib.Path(sum_path).write_text(
                s_text + (("\n\nالكلمات المفتاحية: " + (kw_csv or "")) if kw_csv else ""),
                encoding="utf-8",
            )
        except Exception:
            sum_path = None
        from urllib.parse import quote
        base = settings.BASE_URL.rstrip("/") or str(request.base_url).rstrip("/")
        summary_url = f"{base}/download?path={quote(sum_path)}" if (base and sum_path) else None
        return JSONResponse({
            "summary": s_text,
            "keywords": kw_csv or "",
            "summary_path": sum_path,
            "summary_source": nlp_core.get_summary_source(),
            "download_urls": {"summary": summary_url},
        })

    import uuid
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {"status": "queued", "result_path": None, "error": None}
    asyncio.create_task(run_summary_job_impl(job_id, body, out_base_path, summary_mode))
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
