# routers/jobs.py
import json

from fastapi import APIRouter
from fastapi.responses import FileResponse

from server.deps import response_error, job_file, JOBS

router = APIRouter()


@router.get("/job/{job_id}")
def job_status(job_id: str):
    meta = JOBS.get(job_id, None)
    file = job_file(job_id)
    if file.exists():
        data = json.loads(file.read_text(encoding="utf-8"))
        return data
    if meta is None:
        return response_error(404, "job_not_found")
    return {"status": meta["status"], "result": {}, "error": meta.get("error") or ""}


@router.get("/job/{job_id}/download")
def job_download(job_id: str):
    p = job_file(job_id)
    if not p.exists():
        return response_error(404, "job_not_ready")
    return FileResponse(p.as_posix(), media_type="application/json", filename=p.name)
