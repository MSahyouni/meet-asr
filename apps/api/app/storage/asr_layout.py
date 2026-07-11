# storage/asr_layout.py — تخطيط حفظ مخرجات ASR والتسجيلات
from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .user_paths import user_asr_job_dir, user_recordings_dir


STORAGE_VERSION = 1


@dataclass(frozen=True)
class AsrStorageLayout:
    """Canonical paths for one ASR job.

    Logged-in user:
      - recordings → data/voices/<user>/recordings/<job_id>.*
      - transcripts → data/outputs/<user>/asr/<job_id>/*

    Anonymous (legacy fallback):
      - everything under data/outputs/asr/<job_id>/
    """

    user_email: Optional[str]
    job_id: str
    job_dir: pathlib.Path
    recordings_dir: pathlib.Path
    manifest_path: pathlib.Path

    @property
    def wav_path(self) -> pathlib.Path:
        return self.recordings_dir / f"{self.job_id}.wav"

    def source_path_for(self, original_name: str) -> pathlib.Path:
        ext = pathlib.Path(original_name or "").suffix or ".bin"
        return self.recordings_dir / f"{self.job_id}_source{ext}"

    @property
    def transcript_path(self) -> pathlib.Path:
        return self.job_dir / "transcript.txt"

    @property
    def segments_path(self) -> pathlib.Path:
        return self.job_dir / "segments.json"

    def is_user_scoped(self) -> bool:
        return bool((self.user_email or "").strip())


def resolve_asr_storage(user_email: Optional[str], job_id: str) -> AsrStorageLayout:
    email = (user_email or "").strip() or None
    job_dir = user_asr_job_dir(email, job_id)
    recordings_dir = user_recordings_dir(email) if email else job_dir
    return AsrStorageLayout(
        user_email=email,
        job_id=job_id,
        job_dir=job_dir,
        recordings_dir=recordings_dir,
        manifest_path=job_dir / "manifest.json",
    )


def write_job_manifest(
    layout: AsrStorageLayout,
    *,
    wav_path: Optional[str] = None,
    source_path: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    layout.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload: Dict[str, Any] = {
        "storage_version": STORAGE_VERSION,
        "job_id": layout.job_id,
        "user_email": layout.user_email,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "paths": {
            "job_dir": layout.job_dir.as_posix(),
            "recordings_dir": layout.recordings_dir.as_posix(),
            "wav": wav_path,
            "source": source_path,
            "transcript": layout.transcript_path.as_posix(),
            "segments": layout.segments_path.as_posix(),
            "manifest": layout.manifest_path.as_posix(),
        },
    }
    if extra:
        payload.update(extra)
    layout.manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return layout.manifest_path.as_posix()
