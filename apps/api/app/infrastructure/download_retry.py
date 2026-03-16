import logging
import os
import time
from typing import Callable, TypeVar


T = TypeVar("T")
log = logging.getLogger("infra.download_retry")


def _as_bool(value: str, default: bool = True) -> bool:
    raw = (value or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def run_with_download_retry(operation: Callable[[], T], label: str, max_attempts: int = 0) -> T:
    """
    Execute a model download/load operation with retry policy.

    Default behavior keeps retrying until success.
    Controls:
      - DOWNLOAD_RETRY_FOREVER (default: 1)
      - DOWNLOAD_MAX_RETRIES (default: 0 -> unlimited when not forever)
      - DOWNLOAD_RETRY_BASE_SEC (default: 5)
      - DOWNLOAD_RETRY_MAX_SEC (default: 60)
      - max_attempts (function arg): overrides env if > 0
    """
    forever = _as_bool(os.getenv("DOWNLOAD_RETRY_FOREVER", "1"), default=True)
    env_max_retries = max(0, int(os.getenv("DOWNLOAD_MAX_RETRIES", "0") or "0"))
    if max_attempts > 0:
        max_retries = max_attempts
        forever = False
    else:
        max_retries = env_max_retries
    base_wait = max(1, int(os.getenv("DOWNLOAD_RETRY_BASE_SEC", "5") or "5"))
    max_wait = max(base_wait, int(os.getenv("DOWNLOAD_RETRY_MAX_SEC", "60") or "60"))

    attempt = 0
    while True:
        try:
            return operation()
        except Exception as exc:
            attempt += 1
            if not forever and max_retries > 0 and attempt >= max_retries:
                log.error("[%s] download failed after %s attempts: %s", label, attempt, exc)
                raise

            wait_s = min(max_wait, base_wait * (2 ** min(attempt - 1, 5)))
            log.warning(
                "[%s] download/load attempt %s failed: %s | retrying in %ss",
                label,
                attempt,
                exc,
                wait_s,
            )
            time.sleep(wait_s)
