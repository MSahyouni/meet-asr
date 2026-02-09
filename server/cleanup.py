# server/cleanup.py — حذف مخرجات قديمة تحت outputs/ (بدون الخروج عن المسار)
import logging
import time
from pathlib import Path

from config import settings

logger = logging.getLogger("cleanup")

# Only allow deletion under this base (safety)
OUTPUTS_BASE = settings.OUTPUTS_DIR.resolve()


def _is_safe_under_outputs(path: Path) -> bool:
    """True only if path is under OUTPUTS_DIR (no traversal)."""
    try:
        resolved = path.resolve()
        return OUTPUTS_BASE in resolved.parents or resolved.parent == OUTPUTS_BASE
    except Exception:
        return False


def cleanup_old_outputs(max_age_hours: float = None) -> int:
    """
    Delete files under settings.OUTPUTS_DIR older than max_age_hours.
    Returns number of files deleted. Does NOT delete outside OUTPUTS_DIR.
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
                if not f.is_file():
                    continue
                if not _is_safe_under_outputs(f):
                    continue
                try:
                    if f.stat().st_mtime < cutoff:
                        f.unlink()
                        deleted += 1
                except OSError as e:
                    logger.debug("cleanup skip %s: %s", f, e)
        except OSError as e:
            logger.warning("cleanup dir %s: %s", dir_path, e)
    if deleted:
        logger.info("cleanup deleted %d file(s) older than %s h under outputs/", deleted, max_age_hours)
    return deleted
