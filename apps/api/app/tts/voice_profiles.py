import pathlib
import re
from typing import Optional

from app.config import settings


_SAFE_SLUG_RE = re.compile(r"[^a-z0-9_.-]+")
_ALLOWED_AUDIO_EXT = {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".aac", ".opus"}


def sanitize_user_key(user_email: str) -> str:
    raw = (user_email or "").strip().lower()
    if not raw:
        raise ValueError("user_email is required")
    key = _SAFE_SLUG_RE.sub("_", raw).strip("._-")
    if not key:
        raise ValueError("invalid user_email")
    return key[:96]


def user_voice_dir(user_email: str) -> pathlib.Path:
    base = settings.SPK_DIR.resolve()
    key = sanitize_user_key(user_email)
    path = (base / key).resolve()
    if base not in path.parents and path != base:
        raise ValueError("invalid user voice directory")
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_user_speaker_path(user_email: str, speaker_ref: Optional[str] = None) -> pathlib.Path:
    directory = user_voice_dir(user_email)
    ref = (speaker_ref or "").strip()
    if not ref:
        default_candidate = (directory / "voice.wav").resolve()
        if default_candidate.exists() and default_candidate.is_file():
            return default_candidate
        files = [p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in _ALLOWED_AUDIO_EXT]
        if files:
            return sorted(files, key=lambda p: p.name.lower())[0]
        ref = "voice.wav"
    ref_name = pathlib.Path(ref).name
    candidate = (directory / ref_name).resolve()
    if directory not in candidate.parents and candidate.parent != directory:
        raise ValueError("invalid speaker_ref path")
    if candidate.suffix.lower() not in _ALLOWED_AUDIO_EXT:
        raise ValueError("unsupported speaker file extension")
    return candidate


def save_user_speaker_sample(user_email: str, content: bytes, filename: Optional[str] = None) -> pathlib.Path:
    if not content:
        raise ValueError("empty audio sample")
    target = resolve_user_speaker_path(user_email=user_email, speaker_ref=filename or "voice.wav")
    target.write_bytes(content)
    return target


def list_user_speaker_samples(user_email: str) -> list[pathlib.Path]:
    directory = user_voice_dir(user_email)
    files = [p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in _ALLOWED_AUDIO_EXT]
    return sorted(files, key=lambda p: p.name.lower())


def delete_user_speaker_sample(user_email: str, speaker_ref: str) -> bool:
    path = resolve_user_speaker_path(user_email=user_email, speaker_ref=speaker_ref)
    if not path.exists() or not path.is_file():
        return False
    path.unlink()
    return True
