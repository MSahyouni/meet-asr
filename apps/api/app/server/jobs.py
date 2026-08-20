# server/jobs.py — تخزين المهام الخلفية مع استمرارية واستئناف بعد إعادة التشغيل
from __future__ import annotations

import asyncio
import json
import logging
import pathlib
import shutil
from typing import Any, Callable, Dict, List, Optional

from ..config import settings
from .. import nlp_core
from ..storage.user_paths import user_jobs_dir, user_outputs_root

logger = logging.getLogger(__name__)

JOBS_DIR: pathlib.Path = settings.OUTPUTS_DIR / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)

JOBS: dict = {}

INTERRUPTED_ERROR = "interrupted_by_restart"

_RESUME_KEYS = (
    "job_type",
    "input_paths",
    "kwargs",
    "summary_body",
    "summary_mode",
    "out_base_path",
)

# P2-4: limit concurrent transcribe jobs (in-memory semaphore per process)
_transcribe_semaphore: Optional[asyncio.Semaphore] = None


def get_transcribe_semaphore() -> asyncio.Semaphore:
    global _transcribe_semaphore
    if _transcribe_semaphore is None:
        n = getattr(settings, "TRANSCRIBE_MAX_CONCURRENT", 2)
        _transcribe_semaphore = asyncio.Semaphore(max(1, n))
    return _transcribe_semaphore


def job_payload(
    status: str,
    result: Optional[dict] = None,
    error: Optional[str] = None,
    user_email: Optional[str] = None,
) -> dict:
    payload = {"status": status, "result": result or {}, "error": error or ""}
    if user_email:
        payload["user_email"] = user_email
    return payload


def job_file(job_id: str, user_email: Optional[str] = None) -> pathlib.Path:
    """Path used when writing a job record (known user preferred, else global jobs dir)."""
    if user_email is None:
        meta = JOBS.get(job_id) or {}
        user_email = meta.get("user_email")
    base = user_jobs_dir(user_email) if user_email else JOBS_DIR
    return base / f"{job_id}.json"


def job_staging_dir(job_id: str, user_email: Optional[str] = None) -> pathlib.Path:
    """Durable upload dir kept until the job finishes (survives process restart)."""
    if user_email:
        base = user_outputs_root(user_email) / "jobs_staging" / job_id
    else:
        base = settings.OUTPUTS_DIR / "jobs_staging" / job_id
    base.mkdir(parents=True, exist_ok=True)
    return base.resolve()


def stage_job_inputs(
    job_id: str,
    source_paths: List[pathlib.Path],
    user_email: Optional[str] = None,
) -> List[pathlib.Path]:
    """Move/copy upload files into durable staging and return staged paths."""
    staging = job_staging_dir(job_id, user_email)
    staged: List[pathlib.Path] = []
    for idx, src in enumerate(source_paths):
        src_path = pathlib.Path(src)
        dest = staging / (src_path.name or f"audio_{idx}.wav")
        if dest.exists() and dest.resolve() == src_path.resolve():
            staged.append(dest)
            continue
        try:
            shutil.move(str(src_path), str(dest))
        except OSError:
            shutil.copy2(str(src_path), str(dest))
        staged.append(dest)
    return staged


def cleanup_job_staging(job_id: str, user_email: Optional[str] = None) -> None:
    try:
        staging = job_staging_dir(job_id, user_email)
        shutil.rmtree(staging, ignore_errors=True)
        # Remove empty parent jobs_staging if possible
        parent = staging.parent
        if parent.exists() and parent.name == "jobs_staging" and not any(parent.iterdir()):
            parent.rmdir()
    except OSError:
        pass


def find_job_file(job_id: str, user_email: Optional[str] = None) -> Optional[pathlib.Path]:
    """Locate an existing job JSON on disk (memory hint, then scan outputs)."""
    if user_email is None:
        meta = JOBS.get(job_id) or {}
        user_email = meta.get("user_email")

    candidates: List[pathlib.Path] = []
    if user_email:
        candidates.append(user_jobs_dir(user_email) / f"{job_id}.json")
    candidates.append(JOBS_DIR / f"{job_id}.json")

    for path in candidates:
        if path.exists():
            return path

    try:
        for path in settings.OUTPUTS_DIR.glob(f"*/jobs/{job_id}.json"):
            if path.is_file():
                return path
    except OSError:
        pass
    return None


def set_job(
    job_id: str,
    *,
    status: str,
    user_email: Optional[str] = None,
    result: Optional[dict] = None,
    error: Optional[str] = None,
    resume: Optional[dict] = None,
) -> pathlib.Path:
    """Update in-memory JOBS and persist status (+ optional resume metadata) to disk."""
    existing = load_job_payload(job_id, user_email) or {}
    if user_email is None:
        user_email = (JOBS.get(job_id) or {}).get("user_email") or existing.get("user_email")

    out = job_file(job_id, user_email)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = job_payload(status, result, error, user_email=user_email)

    terminal = status in ("done", "error")
    if not terminal:
        resume_data = resume if resume is not None else {
            key: existing.get(key) for key in _RESUME_KEYS if existing.get(key) is not None
        }
        for key, value in (resume_data or {}).items():
            if value is not None and key in _RESUME_KEYS:
                payload[key] = value

    out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    JOBS[job_id] = {
        "status": status,
        "result_path": out.as_posix() if terminal else None,
        "error": error,
        "user_email": user_email,
    }
    return out


def load_job_payload(job_id: str, user_email: Optional[str] = None) -> Optional[dict]:
    path = find_job_file(job_id, user_email)
    if path is None or not path.exists():
        return None
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def _iter_job_files() -> List[pathlib.Path]:
    files: List[pathlib.Path] = []
    try:
        files.extend(p for p in JOBS_DIR.glob("*.json") if p.is_file())
    except OSError:
        pass
    try:
        files.extend(p for p in settings.OUTPUTS_DIR.glob("*/jobs/*.json") if p.is_file())
    except OSError:
        pass
    seen = set()
    unique: List[pathlib.Path] = []
    for path in files:
        key = path.resolve().as_posix()
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def _can_resume(data: dict) -> bool:
    job_type = str(data.get("job_type") or "").strip()
    if job_type == "summary":
        return data.get("summary_body") is not None and bool(data.get("out_base_path"))
    if job_type in ("transcribe", "transcribe_batch"):
        paths = data.get("input_paths") or []
        if not isinstance(paths, list) or not paths:
            return False
        return all(pathlib.Path(str(p)).exists() for p in paths)
    return False


def reload_jobs_from_disk() -> dict:
    """
    Restore JOBS from on-disk JSON after process restart.

    Queued/running jobs with durable staging + resume metadata are re-queued.
    Otherwise they are marked error: interrupted_by_restart.
    """
    loaded = 0
    interrupted = 0
    pending: List[Dict[str, Any]] = []

    for path in _iter_job_files():
        job_id = path.stem
        try:
            raw = path.read_text(encoding="utf-8").strip()
            if not raw:
                continue
            data = json.loads(raw)
            if not isinstance(data, dict):
                continue
        except (OSError, json.JSONDecodeError):
            continue

        status = str(data.get("status") or "").strip().lower() or "unknown"
        user_email = data.get("user_email") or None
        error = data.get("error") or None
        result = data.get("result") if isinstance(data.get("result"), dict) else {}

        if status in ("queued", "running"):
            if _can_resume(data):
                resume = {key: data.get(key) for key in _RESUME_KEYS if data.get(key) is not None}
                set_job(job_id, status="queued", user_email=user_email, resume=resume)
                pending.append({"job_id": job_id, **resume, "user_email": user_email})
            else:
                set_job(
                    job_id,
                    status="error",
                    user_email=user_email,
                    result=result,
                    error=INTERRUPTED_ERROR,
                )
                interrupted += 1
                cleanup_job_staging(job_id, user_email)
        else:
            JOBS[job_id] = {
                "status": status,
                "result_path": path.as_posix(),
                "error": error,
                "user_email": user_email,
            }
            loaded += 1

    logger.info(
        "Reloaded jobs from disk: restored=%s interrupted=%s resumable=%s",
        loaded,
        interrupted,
        len(pending),
    )
    return {"restored": loaded, "interrupted": interrupted, "pending": pending}


def schedule_resumed_jobs(pending: List[Dict[str, Any]], get_core: Callable[[], Any]) -> int:
    """Create asyncio tasks for jobs returned by reload_jobs_from_disk()['pending']."""
    scheduled = 0
    for item in pending or []:
        job_id = item.get("job_id")
        job_type = item.get("job_type")
        user_email = item.get("user_email")
        if not job_id or not job_type:
            continue
        try:
            if job_type == "transcribe":
                paths = [pathlib.Path(p) for p in (item.get("input_paths") or [])]
                kwargs = dict(item.get("kwargs") or {})
                if not paths:
                    continue
                asyncio.create_task(run_transcribe_job(job_id, paths[0], kwargs, get_core))
                scheduled += 1
            elif job_type == "transcribe_batch":
                paths = [pathlib.Path(p) for p in (item.get("input_paths") or [])]
                kwargs = dict(item.get("kwargs") or {})
                if not paths:
                    continue
                asyncio.create_task(run_transcribe_batch_job(job_id, paths, kwargs, get_core))
                scheduled += 1
            elif job_type == "summary":
                body = str(item.get("summary_body") or "")
                out_base = pathlib.Path(str(item.get("out_base_path")))
                mode = str(item.get("summary_mode") or "jais")
                asyncio.create_task(
                    run_summary_job(job_id, body, out_base, mode, user_email=user_email)
                )
                scheduled += 1
        except Exception as exc:
            logger.warning("Failed to resume job %s: %s", job_id, exc)
            set_job(job_id, status="error", user_email=user_email, error=str(exc))
    return scheduled


async def run_transcribe_job(
    job_id: str,
    tmp_path: pathlib.Path,
    kwargs: dict,
    get_core: Callable[[], Any],
) -> None:
    sem = get_transcribe_semaphore()
    async with sem:
        core = get_core()
        user_email = kwargs.get("user_email")
        set_job(
            job_id,
            status="running",
            user_email=user_email,
            resume={
                "job_type": "transcribe",
                "input_paths": [str(tmp_path)],
                "kwargs": kwargs,
            },
        )
        try:
            result = await asyncio.to_thread(core.process, str(tmp_path), **kwargs)
            if not isinstance(result, dict):
                raise RuntimeError("unexpected_result_type")
            set_job(
                job_id,
                status="done",
                user_email=user_email,
                result=result,
            )
        except Exception as e:
            set_job(
                job_id,
                status="error",
                user_email=user_email,
                error=str(e),
            )
        finally:
            cleanup_job_staging(job_id, user_email)
            try:
                # Legacy tempfile cleanup (non-staging uploads)
                if tmp_path.exists() and "jobs_staging" not in tmp_path.as_posix():
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
    user_email: Optional[str] = None,
) -> None:
    set_job(
        job_id,
        status="running",
        user_email=user_email,
        resume={
            "job_type": "summary",
            "summary_body": body,
            "summary_mode": summary_mode,
            "out_base_path": str(out_base_path),
        },
    )
    try:
        s_text, kw_csv = nlp_core.summarize(body, mode=summary_mode)
        if not s_text.strip():
            result = {
                "summary": "",
                "keywords": "",
                "summary_path": None,
                "summary_docx_path": None,
                "summary_source": "off",
            }
        else:
            from app.asr.docx_export import write_summary_artifacts

            sum_path, sum_docx_path = write_summary_artifacts(
                out_base_path, s_text, kw_csv or ""
            )
            result = {
                "summary": s_text,
                "keywords": kw_csv or "",
                "summary_path": sum_path,
                "summary_docx_path": sum_docx_path,
                "summary_source": nlp_core.get_summary_source(),
            }
        set_job(job_id, status="done", user_email=user_email, result=result)
    except Exception as e:
        set_job(job_id, status="error", user_email=user_email, error=str(e))


async def run_transcribe_batch_job(
    job_id: str,
    file_paths: List[pathlib.Path],
    kwargs: dict,
    get_core: Callable[[], Any],
) -> None:
    sem = get_transcribe_semaphore()
    async with sem:
        core = get_core()
        user_email = kwargs.get("user_email")
        set_job(
            job_id,
            status="running",
            user_email=user_email,
            resume={
                "job_type": "transcribe_batch",
                "input_paths": [str(p) for p in file_paths],
                "kwargs": kwargs,
            },
        )
        try:
            result = await asyncio.to_thread(core.process_many, [str(p) for p in file_paths], **kwargs)
            if not isinstance(result, dict):
                raise RuntimeError("unexpected_result_type")

            merged_text = result.get("text", "")
            merged_path = result.get("txt_path")
            merged_sum = result.get("summary", "") or ""
            keywords = result.get("keywords", "") or ""
            merged_sum_path = result.get("summary_path")
            merged_sum_docx_path = result.get("summary_docx_path")

            summary_mode = str(kwargs.get("summary_mode") or "off").lower()
            if summary_mode != "off":
                if not (merged_sum or "").strip():
                    s_text, kw_csv = nlp_core.summarize(merged_text, mode=summary_mode)
                    merged_sum, keywords = s_text, kw_csv
                try:
                    if (merged_sum or "").strip() and merged_path:
                        from app.asr.docx_export import write_summary_artifacts

                        sum_path, sum_docx_path = write_summary_artifacts(
                            merged_path, merged_sum, keywords or ""
                        )
                        merged_sum_path = sum_path
                        merged_sum_docx_path = sum_docx_path
                except Exception:
                    pass
            else:
                nlp_core.set_summary_source("off")

            payload_result = dict(result)
            payload_result["summary"] = merged_sum
            payload_result["keywords"] = keywords
            payload_result["summary_path"] = merged_sum_path
            payload_result["summary_docx_path"] = merged_sum_docx_path

            set_job(
                job_id,
                status="done",
                user_email=user_email,
                result=payload_result,
            )
        except Exception as e:
            set_job(
                job_id,
                status="error",
                user_email=user_email,
                error=str(e),
            )
        finally:
            cleanup_job_staging(job_id, user_email)
            try:
                for d in {p.parent for p in file_paths if p is not None}:
                    if "jobs_staging" not in d.as_posix():
                        shutil.rmtree(d, ignore_errors=True)
            except Exception:
                pass
