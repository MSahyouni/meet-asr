"""OmniVoice model download and cache cleanup (CLI + API)."""

from __future__ import annotations

import argparse
import os
import pathlib
import sys

from app.config import settings
from app.infrastructure.hf_cache import download_snapshot, remove_stale_incomplete_blobs

OMNIVOICE_REPO_ID = "k2-fsa/OmniVoice"
OMNIVOICE_CACHE_DIRNAME = "models--k2-fsa--OmniVoice"
OMNIVOICE_MODEL_MIN_BYTES = 1_000_000_000


def omnivoice_cache_dirs() -> list[pathlib.Path]:
    return [
        settings.HF_DIR / "hub" / OMNIVOICE_CACHE_DIRNAME,
        settings.HF_DIR / OMNIVOICE_CACHE_DIRNAME,
    ]


def omnivoice_snapshot_model() -> pathlib.Path | None:
    for cache_dir in omnivoice_cache_dirs():
        snap_root = cache_dir / "snapshots"
        if not snap_root.is_dir():
            continue
        for snap in snap_root.iterdir():
            if not snap.is_dir():
                continue
            model_file = snap / "model.safetensors"
            try:
                if model_file.is_file() and model_file.stat().st_size >= OMNIVOICE_MODEL_MIN_BYTES:
                    return model_file
            except OSError:
                continue
    return None


def cleanup_omnivoice_stale_incomplete() -> int:
    return remove_stale_incomplete_blobs(
        omnivoice_cache_dirs(),
        snapshot_ready=lambda: omnivoice_snapshot_model() is not None,
    )


def ensure_omnivoice_model() -> pathlib.Path:
    model_file = omnivoice_snapshot_model()
    if model_file is not None:
        cleanup_omnivoice_stale_incomplete()
        return model_file

    path = download_snapshot(
        OMNIVOICE_REPO_ID,
        label="tts:omnivoice",
        cache_dir=settings.HF_DIR,
        max_workers=max(1, int(os.getenv("DOWNLOAD_MAX_WORKERS", "1") or "1")),
    )
    cleanup_omnivoice_stale_incomplete()
    model_file = omnivoice_snapshot_model()
    if model_file is None:
        raise RuntimeError(f"OmniVoice download finished but model.safetensors not found under {path}")
    return model_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download or clean OmniVoice HF cache")
    parser.add_argument(
        "--cleanup-only",
        action="store_true",
        help="Remove stale .incomplete blobs when snapshot is ready",
    )
    args = parser.parse_args(argv)

    if args.cleanup_only:
        removed = cleanup_omnivoice_stale_incomplete()
        if removed:
            print(f"[cleanup] removed {removed} stale incomplete blob(s)")
        else:
            print("[cleanup] nothing to remove (snapshot missing or no stale blobs)")
        return 0

    model_file = ensure_omnivoice_model()
    print("OK:", model_file.parent.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
