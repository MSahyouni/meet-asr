# storage/user_paths.py — مسارات التخزين لكل مستخدم
from __future__ import annotations

import pathlib
from typing import Optional

from app.config import settings
from app.tts.voice_profiles import sanitize_user_key


class UserEmailMismatchError(ValueError):
    """Raised when form user_email does not match JWT subject."""


def resolve_user_email(
    claimed: Optional[str],
    authorization: Optional[str] = None,
) -> Optional[str]:
    """Prefer JWT email; fall back to client-supplied user_email when no token."""
    from app.features.auth.security import resolve_email_from_authorization

    token_email = resolve_email_from_authorization(authorization)
    claimed_email = (claimed or "").strip() or None
    if token_email:
        if claimed_email and claimed_email.lower() != token_email.lower():
            raise UserEmailMismatchError("user_email does not match logged-in user")
        return token_email
    return claimed_email


def user_outputs_root(user_email: str) -> pathlib.Path:
    root = (settings.OUTPUTS_DIR / sanitize_user_key(user_email)).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def user_asr_job_dir(user_email: Optional[str], job_id: str) -> pathlib.Path:
    if user_email:
        job_dir = user_outputs_root(user_email) / "asr" / job_id
    else:
        job_dir = settings.OUTPUTS_DIR / "asr" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    return job_dir.resolve()


def user_recordings_dir(user_email: str) -> pathlib.Path:
    rec_dir = (settings.SPK_DIR / sanitize_user_key(user_email) / "recordings").resolve()
    rec_dir.mkdir(parents=True, exist_ok=True)
    return rec_dir


def user_speakers_root(user_email: str) -> pathlib.Path:
    """Per-account speaker fingerprints: data/voices/<user>/speakers/"""
    email = (user_email or "").strip()
    if not email:
        raise ValueError("user_email is required")
    speakers_dir = (settings.SPK_DIR / sanitize_user_key(email) / "speakers").resolve()
    speakers_dir.mkdir(parents=True, exist_ok=True)
    return speakers_dir


def speaker_enrollment_dir(user_email: Optional[str], speaker_name: str) -> pathlib.Path:
    """Per-user speaker dir: data/voices/<user>/speakers/<speaker_name>/"""
    name = (speaker_name or "").strip()
    if not name:
        raise ValueError("speaker name is required")
    base = user_speakers_root(user_email or "")
    target = (base / name).resolve()
    if base not in target.parents and target.parent != base:
        raise ValueError("invalid speaker name")
    return target


def user_tts_output_dir(user_email: Optional[str] = None) -> pathlib.Path:
    if user_email:
        out_dir = user_outputs_root(user_email) / "tts"
    else:
        out_dir = settings.OUTPUTS_DIR / "tts"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir.resolve()


def user_jobs_dir(user_email: Optional[str] = None) -> pathlib.Path:
    if user_email:
        jobs_dir = user_outputs_root(user_email) / "jobs"
    else:
        jobs_dir = settings.OUTPUTS_DIR / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    return jobs_dir.resolve()


def is_under_outputs(path: pathlib.Path) -> bool:
    base = settings.OUTPUTS_DIR.resolve()
    try:
        path.resolve().relative_to(base)
        return True
    except ValueError:
        return False


def is_under_user_recordings(path: pathlib.Path) -> bool:
    base = settings.SPK_DIR.resolve()
    try:
        rel = path.resolve().relative_to(base)
    except ValueError:
        return False
    parts = rel.parts
    return len(parts) >= 3 and parts[1] == "recordings"
