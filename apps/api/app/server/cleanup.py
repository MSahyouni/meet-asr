# server/cleanup.py — حذف مخرجات قديمة تحت outputs/ (بدون الخروج عن المسار)
import logging
import shutil
import time
from pathlib import Path

from app.config import settings

logger = logging.getLogger("cleanup")

# Only allow deletion under this base (safety)
OUTPUTS_BASE = settings.OUTPUTS_DIR.resolve()


def _is_safe_under_outputs(path: Path) -> bool:
    """True only if path is under OUTPUTS_DIR (no traversal)."""
    try:
        resolved = path.resolve()
        return resolved == OUTPUTS_BASE or OUTPUTS_BASE in resolved.parents
    except Exception:
        return False


def _mtime_for_path(p: Path) -> float:
    """Return mtime for file, or max mtime of contents for directory."""
    if p.is_file():
        return p.stat().st_mtime
    if p.is_dir():
        try:
            return max((c.stat().st_mtime for c in p.iterdir() if _is_safe_under_outputs(c)), default=p.stat().st_mtime)
        except OSError:
            return p.stat().st_mtime
    return 0.0


def cleanup_old_outputs(max_age_hours: float = None) -> int:
    """
    Delete files/dirs under settings.OUTPUTS_DIR older than max_age_hours.
    Returns number of items deleted. Does NOT delete outside OUTPUTS_DIR.
    Handles asr/<job_id>/ dirs: deletes whole dir when oldest content exceeds cutoff.
    """
    if max_age_hours is None:
        max_age_hours = settings.CLEANUP_MAX_AGE_HOURS
    cutoff = time.time() - (max_age_hours * 3600)
    deleted = 0
    if not OUTPUTS_BASE.exists():
        return 0
    for subdir in ("tts", "jobs", "asr", "manual_summary"):
        dir_path = OUTPUTS_BASE / subdir
        if not dir_path.is_dir():
            continue
        try:
            for f in dir_path.iterdir():
                if not _is_safe_under_outputs(f):
                    continue
                try:
                    m = _mtime_for_path(f)
                    if m < cutoff:
                        if f.is_dir():
                            shutil.rmtree(f, ignore_errors=True)
                        else:
                            f.unlink()
                        deleted += 1
                except OSError as e:
                    logger.debug("cleanup skip %s: %s", f, e)
        except OSError as e:
            logger.warning("cleanup dir %s: %s", dir_path, e)
    if deleted:
        logger.info("cleanup deleted %d item(s) older than %s h under outputs/", deleted, max_age_hours)
    return deleted
