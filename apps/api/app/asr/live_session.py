"""Pseudo-streaming live ASR sessions — temp-only until user opts to save audio."""
from __future__ import annotations

import json
import logging
import pathlib
import shutil
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from app.config import settings
from app.storage.naming import new_timestamped_id
from app.storage.user_paths import user_recordings_dir

logger = logging.getLogger("asr.live_session")

SESSION_TTL_SEC = 3600
LIVE_WINDOW_SEC = 12.0
COMMIT_STEP_SEC = 6.0
_LOCK = threading.RLock()
_SESSIONS: Dict[str, "LiveSession"] = {}
_WARMUP_LOCK = threading.Lock()
_WARMUP_DONE = False


def _live_root() -> pathlib.Path:
    root = (settings.DATA_DIR / "live_asr").resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


@dataclass
class LiveSession:
    session_id: str
    user_email: Optional[str]
    created_at: float
    updated_at: float
    dir: pathlib.Path
    committed_text: str = ""
    partial_text: str = ""
    committed_until_sec: float = 0.0
    finalized: bool = False
    saved: bool = False
    whisper_mode: str = "normal"
    device: Optional[str] = None
    compute_type: Optional[str] = None
    lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def source_path(self) -> pathlib.Path:
        return self.dir / "latest.webm"

    @property
    def wav_path(self) -> pathlib.Path:
        return self.dir / "latest.wav"

    @property
    def meta_path(self) -> pathlib.Path:
        return self.dir / "meta.json"

    def display_text(self) -> str:
        committed = (self.committed_text or "").strip()
        partial = (self.partial_text or "").strip()
        if committed and partial:
            return f"{committed} {partial}".strip()
        return committed or partial

    def touch(self) -> None:
        self.updated_at = time.time()

    def write_meta(self) -> None:
        payload = {
            "session_id": self.session_id,
            "user_email": self.user_email,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "committed_text": self.committed_text,
            "partial_text": self.partial_text,
            "committed_until_sec": self.committed_until_sec,
            "finalized": self.finalized,
            "saved": self.saved,
            "whisper_mode": self.whisper_mode,
        }
        self.meta_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def cleanup_expired_sessions() -> int:
    now = time.time()
    removed = 0
    with _LOCK:
        dead = [sid for sid, s in _SESSIONS.items() if now - s.updated_at > SESSION_TTL_SEC]
        for sid in dead:
            sess = _SESSIONS.pop(sid, None)
            if sess:
                shutil.rmtree(sess.dir, ignore_errors=True)
                removed += 1
    root = _live_root()
    try:
        for child in root.iterdir():
            if not child.is_dir():
                continue
            age = now - child.stat().st_mtime
            if age > SESSION_TTL_SEC and child.name not in _SESSIONS:
                shutil.rmtree(child, ignore_errors=True)
                removed += 1
    except OSError:
        pass
    return removed


def create_session(
    user_email: Optional[str],
    *,
    whisper_mode: str = "normal",
    device: Optional[str] = None,
    compute_type: Optional[str] = None,
) -> LiveSession:
    cleanup_expired_sessions()
    session_id = uuid.uuid4().hex
    now = time.time()
    sess_dir = (_live_root() / session_id).resolve()
    sess_dir.mkdir(parents=True, exist_ok=True)
    sess = LiveSession(
        session_id=session_id,
        user_email=(user_email or "").strip() or None,
        created_at=now,
        updated_at=now,
        dir=sess_dir,
        whisper_mode=(whisper_mode or "normal").strip() or "normal",
        device=device,
        compute_type=compute_type,
    )
    sess.write_meta()
    with _LOCK:
        _SESSIONS[session_id] = sess
    return sess


def get_session(session_id: str) -> Optional[LiveSession]:
    sid = (session_id or "").strip()
    if not sid:
        return None
    with _LOCK:
        sess = _SESSIONS.get(sid)
    if sess:
        if time.time() - sess.updated_at > SESSION_TTL_SEC:
            delete_session(sid)
            return None
        return sess
    sess_dir = (_live_root() / sid).resolve()
    meta = sess_dir / "meta.json"
    if not meta.exists():
        return None
    try:
        data = json.loads(meta.read_text(encoding="utf-8"))
        sess = LiveSession(
            session_id=sid,
            user_email=(data.get("user_email") or None),
            created_at=float(data.get("created_at") or time.time()),
            updated_at=float(data.get("updated_at") or time.time()),
            dir=sess_dir,
            committed_text=data.get("committed_text") or "",
            partial_text=data.get("partial_text") or "",
            committed_until_sec=float(data.get("committed_until_sec") or 0.0),
            finalized=bool(data.get("finalized")),
            saved=bool(data.get("saved")),
            whisper_mode=(data.get("whisper_mode") or "normal"),
        )
        if time.time() - sess.updated_at > SESSION_TTL_SEC:
            shutil.rmtree(sess_dir, ignore_errors=True)
            return None
        with _LOCK:
            _SESSIONS[sid] = sess
        return sess
    except Exception:
        return None


def delete_session(session_id: str) -> bool:
    sid = (session_id or "").strip()
    with _LOCK:
        sess = _SESSIONS.pop(sid, None)
    path = sess.dir if sess else (_live_root() / sid)
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
        return True
    return bool(sess)


def warmup_whisper(
    *,
    device: Optional[str] = None,
    compute_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Load Whisper into memory so the first live chunk is not cold."""
    global _WARMUP_DONE
    from app.asr.whisper import get_model

    model_name = (getattr(settings, "WHISPER_MODEL", None) or "light").strip() or "light"
    with _WARMUP_LOCK:
        t0 = time.time()
        get_model(model_name, device=device, compute_type=compute_type)
        _WARMUP_DONE = True
        elapsed = round(time.time() - t0, 3)
        return {
            "ok": True,
            "warm": True,
            "model": model_name,
            "elapsed_sec": elapsed,
            "cached": elapsed < 0.15,
        }


def _slice_wav(wav_path: pathlib.Path, start_sec: float, end_sec: float, out_name: str) -> Optional[pathlib.Path]:
    import soundfile as sf

    if end_sec <= start_sec + 0.05:
        return None
    data, sr = sf.read(str(wav_path), dtype="float32", always_2d=False)
    if getattr(data, "ndim", 1) > 1:
        data = data.mean(axis=1)
    i0 = max(0, int(start_sec * sr))
    i1 = min(len(data), int(end_sec * sr))
    if i1 <= i0:
        return None
    out = wav_path.with_name(out_name)
    sf.write(str(out), data[i0:i1], sr)
    return out


def _trim_wav_tail(wav_path: pathlib.Path, max_sec: float) -> pathlib.Path:
    """Write a tail-only WAV for the live partial window."""
    import soundfile as sf

    info = sf.info(str(wav_path))
    if info.duration <= max_sec + 0.25:
        return wav_path
    data, sr = sf.read(str(wav_path), dtype="float32", always_2d=False)
    if getattr(data, "ndim", 1) > 1:
        data = data.mean(axis=1)
    keep = int(max_sec * sr)
    if keep <= 0 or keep >= len(data):
        return wav_path
    out = wav_path.with_name("window.wav")
    sf.write(str(out), data[-keep:], sr)
    return out


def _transcribe_wav(wav_path: pathlib.Path, sess: LiveSession) -> str:
    from app.asr.whisper import get_model, run_asr

    model_name = (getattr(settings, "WHISPER_MODEL", None) or "light").strip() or "light"
    model = get_model(model_name, device=sess.device, compute_type=sess.compute_type)
    _meta, segments = run_asr(str(wav_path), model, whisper_mode=sess.whisper_mode, multi_speaker=False)
    parts = [(s.get("text") or "").strip() for s in (segments or []) if (s.get("text") or "").strip()]
    return " ".join(parts).strip()


def ingest_cumulative_audio(sess: LiveSession, audio_bytes: bytes, filename: str = "chunk.webm") -> Dict[str, Any]:
    """Overwrite session source with cumulative client blob, convert, ASR, update texts.

    Strategy: keep committed text for audio before the live window; replace partial_text
    with ASR of the last LIVE_WINDOW_SEC to reduce boundary churn.
    """
    if sess.finalized:
        raise ValueError("session already finalized")
    if not audio_bytes:
        raise ValueError("empty audio chunk")

    with sess.lock:
        ext = pathlib.Path(filename or "chunk.webm").suffix.lower() or ".webm"
        allowed = getattr(settings, "ALLOWED_EXT", None) or {
            ".webm", ".wav", ".mp3", ".ogg", ".m4a", ".mp4", ".flac", ".aac", ".opus",
        }
        if ext not in allowed:
            ext = ".webm"
        for old in sess.dir.glob("latest.*"):
            try:
                old.unlink()
            except OSError:
                pass
        source = sess.dir / f"latest{ext}"
        source.write_bytes(audio_bytes)

        from app.asr.audio import to_wav16k
        import soundfile as sf

        tmp_wav = to_wav16k(str(source))
        try:
            shutil.copy2(tmp_wav, sess.wav_path)
        finally:
            try:
                pathlib.Path(tmp_wav).unlink(missing_ok=True)
            except OSError:
                pass

        duration = float(sf.info(str(sess.wav_path)).duration)

        if duration <= LIVE_WINDOW_SEC + 0.35:
            text = _transcribe_wav(sess.wav_path, sess)
            sess.committed_text = ""
            sess.partial_text = text
            sess.committed_until_sec = 0.0
        else:
            target_commit = max(0.0, duration - LIVE_WINDOW_SEC)
            if target_commit >= sess.committed_until_sec + COMMIT_STEP_SEC:
                slice_path = _slice_wav(
                    sess.wav_path,
                    sess.committed_until_sec,
                    target_commit,
                    "commit_slice.wav",
                )
                if slice_path is not None:
                    piece = _transcribe_wav(slice_path, sess)
                    if piece:
                        sess.committed_text = f"{sess.committed_text} {piece}".strip()
                    sess.committed_until_sec = target_commit
            window_path = _trim_wav_tail(sess.wav_path, LIVE_WINDOW_SEC)
            sess.partial_text = _transcribe_wav(window_path, sess)

        sess.touch()
        sess.write_meta()
        return {
            "session_id": sess.session_id,
            "committed_text": sess.committed_text,
            "partial_text": sess.partial_text,
            "committed_until_sec": round(sess.committed_until_sec, 3),
            "text": sess.display_text(),
            "duration_sec": round(duration, 3),
        }


def finalize_session(sess: LiveSession) -> Dict[str, Any]:
    with sess.lock:
        if not sess.wav_path.exists() and not list(sess.dir.glob("latest.*")):
            raise ValueError("no audio in session")
        if not sess.wav_path.exists():
            from app.asr.audio import to_wav16k

            sources = sorted(sess.dir.glob("latest.*"))
            if not sources:
                raise ValueError("no audio in session")
            tmp_wav = to_wav16k(str(sources[0]))
            try:
                shutil.copy2(tmp_wav, sess.wav_path)
            finally:
                try:
                    pathlib.Path(tmp_wav).unlink(missing_ok=True)
                except OSError:
                    pass

        text = _transcribe_wav(sess.wav_path, sess)
        sess.committed_text = text
        sess.partial_text = ""
        import soundfile as sf

        duration = float(sf.info(str(sess.wav_path)).duration) if sess.wav_path.exists() else 0.0
        sess.committed_until_sec = duration
        sess.finalized = True
        sess.touch()
        sess.write_meta()
        return {
            "session_id": sess.session_id,
            "text": text,
            "committed_text": text,
            "partial_text": "",
            "audio_available": sess.wav_path.exists(),
            "duration_sec": round(duration, 3),
            "saved": sess.saved,
        }


def save_session_audio(sess: LiveSession) -> Dict[str, Any]:
    if not sess.finalized:
        raise ValueError("finalize the session before saving audio")
    if not sess.wav_path.exists():
        raise ValueError("no wav available to save")
    email = (sess.user_email or "").strip()
    if not email:
        raise ValueError("user_email required to save recording")

    with sess.lock:
        rec_dir = user_recordings_dir(email)
        job_id = new_timestamped_id("live")
        dest_wav = rec_dir / f"{job_id}.wav"
        shutil.copy2(sess.wav_path, dest_wav)
        sources = list(sess.dir.glob("latest.*"))
        dest_source = None
        if sources:
            src = sources[0]
            dest_source = rec_dir / f"{job_id}_source{src.suffix.lower()}"
            shutil.copy2(src, dest_source)
        sess.saved = True
        sess.touch()
        sess.write_meta()
        return {
            "session_id": sess.session_id,
            "saved": True,
            "wav_path": dest_wav.as_posix(),
            "source_path": dest_source.as_posix() if dest_source else None,
            "download_url": f"/download?path={dest_wav.as_posix()}",
        }


def assert_session_owner(sess: LiveSession, user_email: Optional[str]) -> None:
    claimed = (user_email or "").strip().lower() or None
    owner = (sess.user_email or "").strip().lower() or None
    if owner and claimed and owner != claimed:
        raise PermissionError("session does not belong to this user")
