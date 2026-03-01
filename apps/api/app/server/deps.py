# server/deps.py — تبعيات مشتركة للـ routers
import secrets
import logging
from typing import Any, Optional

limiter = None
logger = logging.getLogger("api.deps")


def set_limiter(l):
    global limiter
    limiter = l


def get_core() -> Any:
    from app import asr_core
    return asr_core


def check_api_key(x_api_key: Optional[str]):
    """Validate API key if settings.API_TOKEN is configured.
    
    Returns:
        JSONResponse with error if invalid, None if valid or no token configured.
    """
    from app.config import settings
    if settings.API_TOKEN and not secrets.compare_digest(x_api_key or "", settings.API_TOKEN):
        return response_error(401, "unauthorized", "invalid api key")
    return None


# إعادة تصدير للمساعدات
from .responses import response_ok, response_error, request_id_var
from .segments import parse_segments, write_segments_json
from .jobs import (
    JOBS_DIR,
    JOBS,
    job_file,
    job_payload,
    run_transcribe_job,
    run_transcribe_batch_job,
    run_summary_job,
)

run_transcribe_job_impl = run_transcribe_job
run_transcribe_batch_job_impl = run_transcribe_batch_job
run_summary_job_impl = run_summary_job
