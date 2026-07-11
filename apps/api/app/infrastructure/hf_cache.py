"""Shared Hugging Face snapshot download and cache maintenance."""

from __future__ import annotations

import logging
import os
import pathlib
from typing import Callable, Iterable, Optional

from huggingface_hub import snapshot_download

from app.config import settings
from app.infrastructure.download_retry import run_with_download_retry

log = logging.getLogger("infra.hf_cache")


def download_snapshot(
    repo_id: str,
    *,
    label: str,
    cache_dir: Optional[pathlib.Path] = None,
    local_dir: Optional[pathlib.Path] = None,
    max_workers: Optional[int] = None,
    token: Optional[str] = None,
    max_attempts: int = 0,
) -> str:
    """Download a HF repo with the shared retry policy used by Whisper/NLP."""
    cache = cache_dir or settings.HF_DIR
    workers = max_workers
    if workers is None:
        workers = max(1, int(os.getenv("DOWNLOAD_MAX_WORKERS", "1") or "1"))

    def _once() -> str:
        kwargs: dict = {
            "repo_id": repo_id,
            "cache_dir": str(cache),
            "max_workers": workers,
        }
        if local_dir is not None:
            kwargs["local_dir"] = str(local_dir)
            kwargs["local_dir_use_symlinks"] = False
        if token:
            kwargs["token"] = token
        return snapshot_download(**kwargs)

    return run_with_download_retry(_once, label, max_attempts=max_attempts)


def iter_incomplete_blobs(cache_dirs: Iterable[pathlib.Path]) -> list[pathlib.Path]:
    incomplete: list[pathlib.Path] = []
    for cache_dir in cache_dirs:
        blobs = cache_dir / "blobs"
        if not blobs.is_dir():
            continue
        for path in blobs.iterdir():
            if path.is_file() and path.name.endswith(".incomplete"):
                incomplete.append(path)
    return incomplete


def remove_stale_incomplete_blobs(
    cache_dirs: Iterable[pathlib.Path],
    *,
    snapshot_ready: Callable[[], bool],
) -> int:
    """
    Delete orphan .incomplete blobs after a successful snapshot download.

    Safe only when snapshot_ready() is True (complete model on disk).
    """
    if not snapshot_ready():
        return 0

    removed = 0
    for path in iter_incomplete_blobs(cache_dirs):
        try:
            path.unlink()
            removed += 1
            log.info("removed stale incomplete blob: %s", path.name)
        except OSError as exc:
            log.warning("failed to remove %s: %s", path, exc)
    return removed
