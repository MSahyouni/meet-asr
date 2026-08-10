# routers/summarize.py
import pathlib
import asyncio
from typing import Optional

from fastapi import APIRouter, Form, File, Header, Request, UploadFile
from fastapi.responses import JSONResponse

from app import nlp_core
from app.config import settings
from app.storage.naming import new_timestamped_id
from app.features.auth.deps import require_logged_in_user
from app.features.dashboard.schema import ActivityType
from app.features.dashboard.service import DashboardService
from app.server.deps import response_error, set_job, run_summary_job_impl, limiter, check_api_key

router = APIRouter()


@router.post("/summarize")
@limiter.limit("12/minute")
async def summarize_after(
    request: Request,
    text: Optional[str] = Form(None),
    path: Optional[str] = Form(None),
    user_email: Optional[str] = Form(None),
    summary_mode: str = Form("ultra"),
    async_mode: bool = Form(False),
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    fake_file: Optional[UploadFile] = File(None),
):
    # دعم JSON إذا لم يكن FormData
    content_type = request.headers.get("content-type", "").lower()
    if "application/json" in content_type and not text:
        try:
            json_body = await request.json()
            text = json_body.get("text") or json_body.get("model_text")
            path = path or json_body.get("path")
            user_email = user_email or json_body.get("user_email")
            summary_mode = json_body.get("summary_mode", "ultra")
            async_mode = json_body.get("async_mode", False)
            if "x_api_key" in json_body:
                x_api_key = json_body.get("x_api_key")
        except Exception:
            pass  # استمر مع القيم الحالية

    # ultra فقط (lite أُزيل؛ القيم القديمة تُحوَّل تلقائياً داخل nlp)
    summary_mode = (summary_mode or "ultra").strip().lower()
    if summary_mode in ("lite", "light", "best", ""):
        summary_mode = "ultra"    
    auth_error = check_api_key(x_api_key)
    if auth_error:
        return auth_error

    resolved_email, login_error = require_logged_in_user(user_email, authorization)
    if login_error:
        return login_error
    user_email = resolved_email

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
        summary_url = f"/download?path={quote(sum_path)}" if sum_path else None
        if user_email:
            try:
                DashboardService.record_activity(
                    user_email=user_email,
                    activity_type=ActivityType.NLP,
                    description="summarize completed",
                    metadata={"mode": "sync", "summary_mode": summary_mode},
                )
            except Exception:
                pass
        return JSONResponse({
            "summary": s_text,
            "keywords": kw_csv or "",
            "summary_path": sum_path,
            "summary_source": nlp_core.get_summary_source(),
            "download_urls": {"summary": summary_url},
        })

    job_id = new_timestamped_id("nlp")
    set_job(
        job_id,
        status="queued",
        user_email=user_email,
        resume={
            "job_type": "summary",
            "summary_body": body,
            "summary_mode": summary_mode,
            "out_base_path": str(out_base_path),
        },
    )
    asyncio.create_task(run_summary_job_impl(job_id, body, out_base_path, summary_mode, user_email=user_email))
    if user_email:
        try:
            DashboardService.record_activity(
                user_email=user_email,
                activity_type=ActivityType.NLP,
                description="summarize queued",
                metadata={"mode": "async", "summary_mode": summary_mode, "job_id": job_id},
            )
        except Exception:
            pass
    base = settings.BASE_URL.rstrip("/") or str(request.base_url).rstrip("/")
    return JSONResponse(
        {
            "job_id": job_id,
            "status": "queued",
            "poll_url": f"/asr/job/{job_id}",
            "result_url": f"{base}/asr/job/{job_id}/download",
        },
        status_code=202,
    )
