import os
import pathlib
import re
import time
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


def _pick_default_sample(directory: pathlib.Path) -> Optional[pathlib.Path]:
    """Prefer the most recently modified audio sample."""
    files = [p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in _ALLOWED_AUDIO_EXT]
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def resolve_user_speaker_path(user_email: str, speaker_ref: Optional[str] = None) -> pathlib.Path:
    directory = user_voice_dir(user_email)
    ref = (speaker_ref or "").strip()
    if not ref:
        picked = _pick_default_sample(directory)
        if picked is not None:
            return picked
        ref = "voice.wav"
    ref_name = pathlib.Path(ref).name
    candidate = (directory / ref_name).resolve()
    if directory not in candidate.parents and candidate.parent != directory:
        raise ValueError("invalid speaker_ref path")
    if candidate.suffix.lower() not in _ALLOWED_AUDIO_EXT:
        raise ValueError("unsupported speaker file extension")
    return candidate


def _unique_target_path(directory: pathlib.Path, filename: str) -> pathlib.Path:
    """Return a writable path under directory; avoid overwriting existing samples."""
    raw_name = pathlib.Path(filename or "voice.wav").name
    stem = pathlib.Path(raw_name).stem or "voice"
    suffix = pathlib.Path(raw_name).suffix.lower() or ".wav"
    if suffix not in _ALLOWED_AUDIO_EXT:
        raise ValueError("unsupported speaker file extension")

    safe_stem = _SAFE_SLUG_RE.sub("_", stem.lower()).strip("._-") or "voice"
    candidate = (directory / f"{safe_stem}{suffix}").resolve()
    if directory not in candidate.parents and candidate.parent != directory:
        raise ValueError("invalid speaker_ref path")
    if not candidate.exists():
        return candidate

    # Lazy import avoids circular import: storage.user_paths → voice_profiles.
    from app.storage.naming import new_timestamped_id

    # Collision: timestamped unique name (keeps original stem for readability).
    unique = new_timestamped_id(safe_stem[:32])
    return (directory / f"{unique}{suffix}").resolve()


def save_user_speaker_sample(user_email: str, content: bytes, filename: Optional[str] = None) -> pathlib.Path:
    if not content:
        raise ValueError("empty audio sample")
    directory = user_voice_dir(user_email)
    target = _unique_target_path(directory, filename or "voice.wav")
    target.write_bytes(content)
    # Touch mtime so "most recent" default picks this upload immediately.
    try:
        now = time.time()
        os.utime(target, (now, now))
    except OSError:
        pass
    return target


def _speaker_ref_text_path(audio_path: pathlib.Path) -> pathlib.Path:
    return audio_path.with_name(f"{audio_path.name}.ref.txt")


def save_user_speaker_ref_text(user_email: str, speaker_ref: str, ref_text: str) -> pathlib.Path:
    target_audio = resolve_user_speaker_path(user_email=user_email, speaker_ref=speaker_ref)
    text_value = (ref_text or "").strip()
    if not text_value:
        raise ValueError("ref_text cannot be empty")
    target_text = _speaker_ref_text_path(target_audio)
    target_text.write_text(text_value, encoding="utf-8")
    return target_text


def get_user_speaker_ref_text(user_email: str, speaker_ref: str) -> Optional[str]:
    target_audio = resolve_user_speaker_path(user_email=user_email, speaker_ref=speaker_ref)
    target_text = _speaker_ref_text_path(target_audio)
    if not target_text.exists() or not target_text.is_file():
        return None
    try:
        value = target_text.read_text(encoding="utf-8").strip()
    except Exception:
        return None
    return value or None


def list_user_speaker_samples(user_email: str) -> list[pathlib.Path]:
    directory = user_voice_dir(user_email)
    files = [p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in _ALLOWED_AUDIO_EXT]
    # Newest first for UI convenience.
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)


def delete_user_speaker_sample(user_email: str, speaker_ref: str) -> bool:
    path = resolve_user_speaker_path(user_email=user_email, speaker_ref=speaker_ref)
    if not path.exists() or not path.is_file():
        return False
    sidecar = _speaker_ref_text_path(path)
    if sidecar.exists() and sidecar.is_file():
        try:
            sidecar.unlink()
        except Exception:
            pass
    path.unlink()
    return True
