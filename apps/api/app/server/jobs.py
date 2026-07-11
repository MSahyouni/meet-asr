# server/jobs.py — تخزين المهام الخلفية (transcribe / summary)
import asyncio
import json
import pathlib
import shutil
from typing import Callable, Any, Optional, List

from ..config import settings
from .. import nlp_core
from ..storage.user_paths import user_jobs_dir

JOBS_DIR: pathlib.Path = settings.OUTPUTS_DIR / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)

JOBS: dict = {}

# P2-4: limit concurrent transcribe jobs (in-memory semaphore per process)
_transcribe_semaphore: Optional[asyncio.Semaphore] = None


def get_transcribe_semaphore() -> asyncio.Semaphore:
    global _transcribe_semaphore
    if _transcribe_semaphore is None:
        n = getattr(settings, "TRANSCRIBE_MAX_CONCURRENT", 2)
        _transcribe_semaphore = asyncio.Semaphore(max(1, n))
    return _transcribe_semaphore


def job_file(job_id: str, user_email: Optional[str] = None) -> pathlib.Path:
    if user_email is None:
        meta = JOBS.get(job_id) or {}
        user_email = meta.get("user_email")
    base = user_jobs_dir(user_email) if user_email else JOBS_DIR
    return base / f"{job_id}.json"


def job_payload(status: str, result: Optional[dict] = None, error: Optional[str] = None) -> dict:
    return {"status": status, "result": result or {}, "error": error or ""}


async def run_transcribe_job(
    job_id: str,
    tmp_path: pathlib.Path,
    kwargs: dict,
    get_core: Callable[[], Any],
) -> None:
    sem = get_transcribe_semaphore()
    async with sem:
        core = get_core()
        JOBS[job_id] = {
            "status": "running",
            "result_path": None,
            "error": None,
            "user_email": kwargs.get("user_email"),
        }
        try:
            result = await asyncio.to_thread(core.process, str(tmp_path), **kwargs)
            if not isinstance(result, dict):
                raise RuntimeError("unexpected_result_type")
            payload = job_payload("done", result, None)
            out = job_file(job_id, kwargs.get("user_email"))
            out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            JOBS[job_id]["status"] = "done"
            JOBS[job_id]["result_path"] = out.as_posix()
        except Exception as e:
            payload = job_payload("error", None, str(e))
            out = job_file(job_id, kwargs.get("user_email"))
            out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            JOBS[job_id]["status"] = "error"
            JOBS[job_id]["error"] = str(e)
        finally:
            try:
                tmp_dir = tmp_path.parent
                tmp_path.unlink(missing_ok=True)
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception:
                pass


async def run_summary_job(
    job_id: str,
    body: str,
    out_base_path: pathlib.Path,
    summary_mode: str,
) -> None:
    try:
        s_text, kw_csv = nlp_core.summarize(body, mode=summary_mode)
        if not s_text.strip():
            payload = job_payload(
                "done",
                {"summary": "", "keywords": "", "summary_path": None, "summary_source": "off"},
            )
        else:
            try:
                sum_path = str(out_base_path.with_suffix(".summary.txt"))
                pathlib.Path(sum_path).write_text(
                    s_text
                    + (("\n\nالكلمات المفتاحية: " + (kw_csv or "")) if kw_csv else ""),
                    encoding="utf-8",
                )
            except Exception:
                sum_path = None
            payload = job_payload(
                "done",
                {
                    "summary": s_text,
                    "keywords": kw_csv or "",
                    "summary_path": sum_path,
                    "summary_source": nlp_core.get_summary_source(),
                },
            )
        out = job_file(job_id)
        out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        JOBS[job_id] = {"status": "done", "result_path": out.as_posix(), "error": None}
    except Exception as e:
        out = job_file(job_id)
        out.write_text(
            json.dumps(job_payload("error", None, str(e)), ensure_ascii=False),
            encoding="utf-8",
        )
        JOBS[job_id] = {"status": "error", "result_path": None, "error": str(e)}


async def run_transcribe_batch_job(
    job_id: str,
    file_paths: List[pathlib.Path],
    kwargs: dict,
    get_core: Callable[[], Any],
) -> None:
    sem = get_transcribe_semaphore()
    async with sem:
        core = get_core()
        JOBS[job_id] = {
            "status": "running",
            "result_path": None,
            "error": None,
            "user_email": kwargs.get("user_email"),
        }
        try:
            result = await asyncio.to_thread(core.process_many, [str(p) for p in file_paths], **kwargs)
            if not isinstance(result, dict):
                raise RuntimeError("unexpected_result_type")

            merged_text = result.get("text", "")
            merged_path = result.get("txt_path")
            merged_sum = result.get("summary", "") or ""
            keywords = result.get("keywords", "") or ""
            merged_sum_path = result.get("summary_path")

            summary_mode = str(kwargs.get("summary_mode") or "off").lower()
            if summary_mode != "off":
                if not (merged_sum or "").strip():
                    s_text, kw_csv = nlp_core.summarize(merged_text, mode=summary_mode)
                    merged_sum, keywords = s_text, kw_csv
                try:
                    if (merged_sum or "").strip() and merged_path:
                        sum_p = pathlib.Path(merged_path).with_suffix(".summary.txt")
                        sum_p.write_text(
                            merged_sum
                            + (("\n\nالكلمات المفتاحية: " + (keywords or "")) if keywords else ""),
                            encoding="utf-8",
                        )
                        merged_sum_path = str(sum_p)
                except Exception:
                    pass
            else:
                nlp_core.set_summary_source("off")

            payload_result = dict(result)
            payload_result["summary"] = merged_sum
            payload_result["keywords"] = keywords
            payload_result["summary_path"] = merged_sum_path

            payload = job_payload("done", payload_result, None)
            out = job_file(job_id, kwargs.get("user_email"))
            out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            JOBS[job_id]["status"] = "done"
            JOBS[job_id]["result_path"] = out.as_posix()
        except Exception as e:
            payload = job_payload("error", None, str(e))
            out = job_file(job_id, kwargs.get("user_email"))
            out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            JOBS[job_id]["status"] = "error"
            JOBS[job_id]["error"] = str(e)
        finally:
            try:
                for d in {p.parent for p in file_paths if p is not None}:
                    shutil.rmtree(d, ignore_errors=True)
            except Exception:
                pass

