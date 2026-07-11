# routers/jobs.py
import json
from json import JSONDecodeError
from typing import Optional

from fastapi import APIRouter, Header
from fastapi.responses import FileResponse

from app.features.auth.deps import require_logged_in_user
from app.server.deps import response_error, job_file, JOBS, check_api_key

router = APIRouter()


def _require_job_auth(authorization: Optional[str], x_api_key: Optional[str]):
    auth_error = check_api_key(x_api_key)
    if auth_error:
        return auth_error
    _, login_error = require_logged_in_user(authorization=authorization)
    if login_error:
        return login_error
    return None


@router.get("/job/{job_id}")
def job_status(
    job_id: str,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    auth_error = _require_job_auth(authorization, x_api_key)
    if auth_error:
        return auth_error
    meta = JOBS.get(job_id, None)
    file = job_file(job_id)
    if file.exists():
        raw = file.read_text(encoding="utf-8").strip()
        if not raw:
            if meta is not None:
                return {"status": meta["status"], "result": {}, "error": meta.get("error") or ""}
            return response_error(404, "job_not_found")
        try:
            data = json.loads(raw)
            return data
        except JSONDecodeError:
            if meta is not None:
                return {"status": meta["status"], "result": {}, "error": meta.get("error") or ""}
            return response_error(404, "job_not_found")
    if meta is None:
        return response_error(404, "job_not_found")
    return {"status": meta["status"], "result": {}, "error": meta.get("error") or ""}


@router.get("/job/{job_id}/download")
def job_download(
    job_id: str,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    auth_error = _require_job_auth(authorization, x_api_key)
    if auth_error:
        return auth_error
    p = job_file(job_id)
    if not p.exists():
        return response_error(404, "job_not_ready")
    return FileResponse(p.as_posix(), media_type="application/json", filename=p.name)
