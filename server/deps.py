# server/deps.py — تبعيات مشتركة للـ routers
from typing import Any

limiter = None


def set_limiter(l):
    global limiter
    limiter = l


def get_core() -> Any:
    import asr_core
    return asr_core


# إعادة تصدير للمساعدات
from server.responses import response_ok, response_error, request_id_var
from server.segments import parse_segments, write_segments_json
from server.jobs import (
    JOBS_DIR,
    JOBS,
    job_file,
    job_payload,
    run_transcribe_job,
    run_summary_job,
)

run_transcribe_job_impl = run_transcribe_job
run_summary_job_impl = run_summary_job
