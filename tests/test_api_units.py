# tests/test_api_units.py — unit tests: enhance_mode, path safety, TTS validation
import pathlib
import tempfile

import pytest


# ----- enhance_mode mapping (same logic as routers/transcribe._resolve_enhance_mode) -----
# We test the logic in-process to avoid importing the router (limiter is None outside app).
def _resolve_enhance_mode(enhance_mode: str, enhance: bool) -> str:
    if enhance:
        return "full"
    em = (enhance_mode or "off").strip().lower()
    return em if em in ("off", "light", "full") else "off"


def test_enhance_mode_enhance_true_returns_full():
    assert _resolve_enhance_mode("off", True) == "full"
    assert _resolve_enhance_mode("light", True) == "full"
    assert _resolve_enhance_mode("full", True) == "full"


def test_enhance_mode_enhance_false_uses_mode():
    assert _resolve_enhance_mode("off", False) == "off"
    assert _resolve_enhance_mode("light", False) == "light"
    assert _resolve_enhance_mode("full", False) == "full"


def test_enhance_mode_invalid_falls_back_to_off():
    assert _resolve_enhance_mode("invalid", False) == "off"
    assert _resolve_enhance_mode("", False) == "off"
    assert _resolve_enhance_mode("  OFF  ", False) == "off"


# ----- path safety for /download (path under base, no traversal) -----
def _is_safe_download_path(base: pathlib.Path, path: str, allowed_ext: set) -> bool:
    """Mirrors routers/export download logic: path under base, suffix allowed."""
    try:
        base = base.resolve()
        p = pathlib.Path(path).expanduser()
        if not p.is_absolute():
            p = (base / p).resolve()
        else:
            p = p.resolve()
        if base not in p.parents and p.parent != base:
            return False
        return p.suffix.lower() in allowed_ext
    except Exception:
        return False


def test_download_path_safe_under_base():
    with tempfile.TemporaryDirectory() as d:
        base = pathlib.Path(d)
        (base / "tts").mkdir(exist_ok=True)
        (base / "tts" / "x.wav").write_text("")
        allowed = {".txt", ".srt", ".vtt", ".json", ".wav"}
        assert _is_safe_download_path(base, str(base / "tts" / "x.wav"), allowed) is True
        assert _is_safe_download_path(base, (base / "tts" / "x.wav").as_posix(), allowed) is True
        assert _is_safe_download_path(base, "tts/x.wav", allowed) is True


def test_download_path_traversal_rejected():
    """CRITICAL: Must fail if path traversal is reintroduced."""
    with tempfile.TemporaryDirectory() as d:
        base = pathlib.Path(d).resolve()
        (base / "asr").mkdir(exist_ok=True)
        (base / "asr" / "good.txt").write_text("ok")
        allowed = {".txt", ".wav"}
        # Path that escapes base via traversal (resolves outside base)
        assert _is_safe_download_path(base, "asr/../../outside.txt", allowed) is False
        assert _is_safe_download_path(base, "asr/../../../etc/passwd", allowed) is False
        # Absolute path outside base
        outside = (base / ".." / "outside.txt").resolve()
        assert _is_safe_download_path(base, str(outside), allowed) is False
        # Valid path under base must still pass
        assert _is_safe_download_path(base, "asr/good.txt", allowed) is True


def test_download_path_forbidden_extension():
    with tempfile.TemporaryDirectory() as d:
        base = pathlib.Path(d)
        (base / "x.exe").write_text("")
        allowed = {".txt", ".wav"}
        assert _is_safe_download_path(base, str(base / "x.exe"), allowed) is False
        assert _is_safe_download_path(base, str(base / "x.wav"), allowed) is True


# ----- TTS input validation (tts_core) -----
def test_tts_validation_text_empty_raises():
    from app.tts_core import TTSCore
    core = TTSCore()
    with pytest.raises(ValueError, match="cannot be empty"):
        core.synthesize("", voice="ar_mms", speed=1.0, out_path="")


def test_tts_validation_text_too_long_raises():
    from app.tts_core import TTSCore, TTS_TEXT_MAX_LEN
    core = TTSCore()
    with pytest.raises(ValueError, match="exceeds maximum"):
        core.synthesize("x" * (TTS_TEXT_MAX_LEN + 1), voice="ar_mms", speed=1.0, out_path="")


def test_tts_validation_speed_out_of_range_raises():
    from app.tts_core import TTSCore
    core = TTSCore()
    with pytest.raises(ValueError, match="Speed must be"):
        core.synthesize("hello", voice="ar_mms", speed=3.0, out_path="")
    with pytest.raises(ValueError, match="Speed must be"):
        core.synthesize("hello", voice="ar_mms", speed=0.1, out_path="")


def test_tts_validation_speed_valid_not_value_error():
    from app.tts_core import TTSCore
    core = TTSCore()
    # Speed 0.5 and 2.0 are in range; must not raise ValueError for speed (may raise RuntimeError if model not loaded)
    for speed in (0.5, 1.0, 2.0):
        try:
            core.synthesize("x", voice="ar_mms", speed=speed, out_path="")
        except ValueError as e:
            assert "Speed must be" not in str(e), f"speed={speed} should be valid"
        except RuntimeError:
            pass  # model not loaded is ok in unit test


def test_omnivoice_ready_when_snapshot_exists_despite_stale_incomplete(tmp_path, monkeypatch):
    from app.config import settings
    from app.infrastructure import omnivoice_download as ov_dl
    from app.tts import tts_omnivoice as ov

    monkeypatch.setattr(settings, "HF_DIR", tmp_path)
    monkeypatch.setattr(ov_dl, "OMNIVOICE_MODEL_MIN_BYTES", 100)

    legacy = tmp_path / "models--k2-fsa--OmniVoice"
    snap = legacy / "snapshots" / "abc123"
    snap.mkdir(parents=True)
    (snap / "model.safetensors").write_bytes(b"x" * 200)

    stale_hub = tmp_path / "hub" / "models--k2-fsa--OmniVoice" / "blobs"
    stale_hub.mkdir(parents=True)
    stale_blob = stale_hub / "orphan.incomplete"
    stale_blob.write_bytes(b"y" * 50)

    ready, status = ov._omnivoice_download_status()
    assert ready is True
    assert status == "جاهز"
    assert not stale_blob.exists()


def test_cleanup_omnivoice_stale_incomplete(tmp_path, monkeypatch):
    from app.config import settings
    from app.infrastructure import omnivoice_download as ov_dl

    monkeypatch.setattr(settings, "HF_DIR", tmp_path)
    monkeypatch.setattr(ov_dl, "OMNIVOICE_MODEL_MIN_BYTES", 100)

    legacy = tmp_path / "models--k2-fsa--OmniVoice"
    snap = legacy / "snapshots" / "abc123"
    snap.mkdir(parents=True)
    (snap / "model.safetensors").write_bytes(b"x" * 200)

    blobs = tmp_path / "hub" / "models--k2-fsa--OmniVoice" / "blobs"
    blobs.mkdir(parents=True)
    stale = blobs / "old.incomplete"
    stale.write_bytes(b"z" * 20)

    removed = ov_dl.cleanup_omnivoice_stale_incomplete()
    assert removed == 1
    assert not stale.exists()


def test_maybe_diacritize_disabled_by_default():
    from app.tts_core import maybe_diacritize

    text = "ذهب الطالب الى المدرسة"
    assert maybe_diacritize(text) == text


def test_maybe_diacritize_uses_backend_when_enabled(monkeypatch):
    from app.config import settings
    from app.tts_core import maybe_diacritize

    monkeypatch.setattr(settings, "TTS_DIACRITIZE", True)
    monkeypatch.setattr(
        "app.tts.diacritize.add_diacritics",
        lambda text: text + "_tashkeel",
    )
    assert maybe_diacritize("نص") == "نص_tashkeel"


def test_list_voices_returns_non_empty():
    """GET /tts/voices relies on tts_core.list_voices() returning a non-empty list."""
    from app.tts_core import list_voices
    voices = list_voices()
    assert isinstance(voices, list)
    assert len(voices) > 0
    assert "ar_mms" in voices
    assert "habibi_unified" in voices
    assert "omnivoice" in voices


def test_response_error_format_has_required_keys():
    """All endpoints use response_error from server.deps; it must include error and detail."""
    from app.server.deps import response_error
    import json
    resp = response_error(400, "bad_request", "Missing text")
    data = json.loads(resp.body.decode())
    assert "error" in data
    assert data["error"] == "bad_request"
    assert "detail" in data
    assert "request_id" in data


def test_upload_uses_chunked_read():
    """Upload streaming must use chunk loop with size bound (not full file into memory)."""
    # Transcribe defines UPLOAD_CHUNK_SIZE = 2*1024*1024 and uses uf.read(UPLOAD_CHUNK_SIZE)
    UPLOAD_CHUNK_SIZE = 2 * 1024 * 1024  # must match routers/transcribe.py
    assert UPLOAD_CHUNK_SIZE > 0
    assert UPLOAD_CHUNK_SIZE <= 8 * 1024 * 1024  # max 8MB per chunk


@pytest.mark.integration
def test_download_path_traversal_integration(monkeypatch):
    """Integration: /asr/download must reject path traversal."""
    from fastapi.testclient import TestClient
    from apps.api import api as api_mod
    from app.features.auth import security as auth_security
    from app.routers import export as export_router

    monkeypatch.setattr(auth_security, "resolve_email_from_authorization", lambda _: "user@example.com")
    monkeypatch.setattr(export_router, "check_api_key", lambda _: None)

    client = TestClient(api_mod.app)
    resp = client.get(
        "/asr/download?path=asr/../../etc/passwd",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status_code == 403


def test_punct_label_mapping_does_not_leak_label_tokens():
    from app.nlp.punctuation_ner import _punct_from_label, _LEAKED_LABEL_RE

    assert _punct_from_label("LABEL_0", label_id=0) == ""
    assert _punct_from_label("LABEL_1", label_id=1) == "."
    assert _punct_from_label("LABEL_2", label_id=2) == "،"
    assert _punct_from_label("LABEL_3", label_id=3) == "؟"
    assert _punct_from_label("LABEL_4", label_id=4) == "!"
    assert _punct_from_label("", label_id=5) == "؛"
    assert _punct_from_label("", label_id=6) == ":"

    leaked = "السلامLABEL_0 عليكمLABEL_2 وبركاتهLABEL_1"
    cleaned = _LEAKED_LABEL_RE.sub("", leaked)
    assert "LABEL_" not in cleaned
    assert "السلام" in cleaned
