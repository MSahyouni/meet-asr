"""Live ASR session: temp-only until save-audio; dismiss purges recordings."""
from __future__ import annotations

import pathlib
import wave

import numpy as np
import pytest


def _write_silence_wav(path: pathlib.Path, seconds: float = 0.4, sr: int = 16000) -> None:
    n = int(sr * seconds)
    pcm = np.zeros(n, dtype=np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())


@pytest.fixture()
def live_mod(tmp_path, monkeypatch):
    monkeypatch.setenv("ASR_DATA_DIR", str(tmp_path))
    from app.config import settings

    monkeypatch.setattr(settings, "DATA_DIR", pathlib.Path(tmp_path))
    monkeypatch.setattr(settings, "SPK_DIR", pathlib.Path(tmp_path) / "voices")
    (pathlib.Path(tmp_path) / "voices").mkdir(parents=True, exist_ok=True)
    from app.asr import live_session as live

    live._SESSIONS.clear()
    yield live
    live._SESSIONS.clear()


def test_create_and_delete_session_purges_temp(live_mod, tmp_path):
    sess = live_mod.create_session("user@example.com", whisper_mode="whisper")
    assert sess.session_id
    assert sess.dir.exists()
    assert (tmp_path / "live_asr" / sess.session_id).exists()
    assert live_mod.delete_session(sess.session_id) is True
    assert not sess.dir.exists()
    assert live_mod.get_session(sess.session_id) is None


def test_save_requires_finalize_and_lands_in_recordings(live_mod, tmp_path, monkeypatch):
    sess = live_mod.create_session("saver@example.com")
    _write_silence_wav(sess.wav_path, seconds=0.3)
    (sess.dir / "latest.webm").write_bytes(b"fake-webm")

    with pytest.raises(ValueError, match="finalize"):
        live_mod.save_session_audio(sess)

    monkeypatch.setattr(live_mod, "_transcribe_wav", lambda wav, s: "نص تجريبي")
    result = live_mod.finalize_session(sess)
    assert result["text"] == "نص تجريبي"
    assert result["audio_available"] is True
    assert sess.finalized is True

    # Before save: nothing under recordings
    rec_root = tmp_path / "voices"
    # user_recordings_dir layout — assert no premature persist under live temp only
    assert list(sess.dir.glob("*.wav"))

    saved = live_mod.save_session_audio(sess)
    assert saved["saved"] is True
    wav_path = pathlib.Path(saved["wav_path"])
    assert wav_path.exists()
    assert "recordings" in wav_path.as_posix()
    assert sess.saved is True


def test_dismiss_without_save_leaves_no_recording(live_mod, tmp_path, monkeypatch):
    sess = live_mod.create_session("discard@example.com")
    _write_silence_wav(sess.wav_path, seconds=0.25)
    monkeypatch.setattr(live_mod, "_transcribe_wav", lambda wav, s: "مؤقت")
    live_mod.finalize_session(sess)
    sid = sess.session_id
    live_mod.delete_session(sid)

    # No promoted recordings for this user
    voices = tmp_path / "voices"
    if voices.exists():
        wavs = list(voices.rglob("*.wav"))
        assert wavs == []
    assert not (tmp_path / "live_asr" / sid).exists()


def test_ingest_cumulative_updates_text(live_mod, tmp_path, monkeypatch):
    sess = live_mod.create_session("chunk@example.com")

    def fake_to_wav16k(src):
        out = pathlib.Path(src).with_suffix(".converted.wav")
        _write_silence_wav(out, seconds=0.5)
        return str(out)

    monkeypatch.setattr("app.asr.audio.to_wav16k", fake_to_wav16k)
    monkeypatch.setattr(live_mod, "_transcribe_wav", lambda wav, s: "مرحبا بالعالم")

    raw = b"RIFF" + b"\x00" * 64  # content irrelevant; to_wav16k mocked
    result = live_mod.ingest_cumulative_audio(sess, raw, filename="chunk.wav")
    assert result["text"] == "مرحبا بالعالم"
    assert sess.partial_text == "مرحبا بالعالم"
    assert sess.committed_text == ""
    assert sess.wav_path.exists()
    assert "live_asr" in sess.wav_path.as_posix()
    assert "recordings" not in sess.wav_path.as_posix()


def test_ingest_sliding_window_commits_prefix(live_mod, tmp_path, monkeypatch):
    sess = live_mod.create_session("window@example.com")

    def fake_to_wav16k(src):
        out = pathlib.Path(src).with_name("converted_long.wav")
        _write_silence_wav(out, seconds=20.0)
        return str(out)

    def fake_asr(wav, s):
        name = pathlib.Path(wav).name
        if name == "commit_slice.wav":
            return "مثبت"
        if name in ("window.wav", "latest.wav", "converted_long.wav"):
            return "نافذة"
        return "؟"

    monkeypatch.setattr("app.asr.audio.to_wav16k", fake_to_wav16k)
    monkeypatch.setattr(live_mod, "_transcribe_wav", fake_asr)

    result = live_mod.ingest_cumulative_audio(sess, b"x", filename="chunk.wav")
    assert sess.committed_until_sec >= live_mod.COMMIT_STEP_SEC
    assert "مثبت" in (result["committed_text"] or "")
    assert result["partial_text"] == "نافذة"
    assert "مثبت" in result["text"] and "نافذة" in result["text"]


def test_warmup_whisper_calls_get_model(live_mod, monkeypatch):
    called = {}

    def fake_get_model(name, device=None, compute_type=None):
        called["name"] = name
        return object()

    monkeypatch.setattr("app.asr.whisper.get_model", fake_get_model)
    out = live_mod.warmup_whisper()
    assert out["warm"] is True
    assert "name" in called
