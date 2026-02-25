# server — وحدات خادم API (استجابات، مقاطع، مهام، تبعيات)
from .responses import request_id_var, response_ok, response_error
from .segments import parse_segments, write_segments_json
from .jobs import JOBS_DIR, JOBS, job_file, job_payload, run_transcribe_job, run_summary_job
from .deps import get_core, set_limiter, limiter

# للتوافق مع من يستدعي run_*_job_impl
run_transcribe_job_impl = run_transcribe_job
run_summary_job_impl = run_summary_job

__all__ = [
    "request_id_var", "response_ok", "response_error",
    "parse_segments", "write_segments_json",
    "JOBS_DIR", "JOBS", "job_file", "job_payload",
    "run_transcribe_job", "run_summary_job",
    "run_transcribe_job_impl", "run_summary_job_impl",
    "get_core", "set_limiter", "limiter",
]
