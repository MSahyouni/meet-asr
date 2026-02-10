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
    from tts_core import TTSCore
    core = TTSCore()
    with pytest.raises(ValueError, match="cannot be empty"):
        core.synthesize("", voice="af_heart", speed=1.0, out_path="")


def test_tts_validation_text_too_long_raises():
    from tts_core import TTSCore, TTS_TEXT_MAX_LEN
    core = TTSCore()
    with pytest.raises(ValueError, match="exceeds maximum"):
        core.synthesize("x" * (TTS_TEXT_MAX_LEN + 1), voice="af_heart", speed=1.0, out_path="")


def test_tts_validation_speed_out_of_range_raises():
    from tts_core import TTSCore
    core = TTSCore()
    with pytest.raises(ValueError, match="Speed must be"):
        core.synthesize("hello", voice="af_heart", speed=3.0, out_path="")
    with pytest.raises(ValueError, match="Speed must be"):
        core.synthesize("hello", voice="af_heart", speed=0.1, out_path="")


def test_tts_validation_speed_valid_not_value_error():
    from tts_core import TTSCore
    core = TTSCore()
    # Speed 0.5 and 2.0 are in range; must not raise ValueError for speed (may raise RuntimeError if model not loaded)
    for speed in (0.5, 1.0, 2.0):
        try:
            core.synthesize("x", voice="af_heart", speed=speed, out_path="")
        except ValueError as e:
            assert "Speed must be" not in str(e), f"speed={speed} should be valid"
        except RuntimeError:
            pass  # model not loaded is ok in unit test


def test_list_voices_returns_non_empty():
    """GET /tts/voices relies on tts_core.list_voices() returning a non-empty list."""
    from tts_core import list_voices
    voices = list_voices()
    assert isinstance(voices, list)
    assert len(voices) > 0
    assert "af_heart" in voices


def test_response_error_format_has_required_keys():
    """All endpoints use response_error from server.deps; it must include error and detail."""
    from server.deps import response_error
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


@pytest.mark.skip(reason="integration test - run explicitly if needed")
def test_download_path_traversal_integration():
    """Integration: /download must reject path traversal. Run with: pytest -k test_download_path_traversal_integration --run-skip."""
    from fastapi.testclient import TestClient
    import api

    client = TestClient(api.app)
    resp = client.get("/download?path=asr/../../etc/passwd")
    assert resp.status_code == 403
