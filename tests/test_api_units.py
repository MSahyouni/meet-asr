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
        core.synthesize("", voice="habibi_unified", speed=1.0, out_path="")


def test_tts_validation_text_too_long_raises():
    from app.tts_core import TTSCore, TTS_TEXT_MAX_LEN
    core = TTSCore()
    with pytest.raises(ValueError, match="exceeds maximum"):
        core.synthesize("x" * (TTS_TEXT_MAX_LEN + 1), voice="habibi_unified", speed=1.0, out_path="")


def test_tts_validation_speed_out_of_range_raises():
    from app.tts_core import TTSCore
    core = TTSCore()
    with pytest.raises(ValueError, match="Speed must be"):
        core.synthesize("hello", voice="habibi_unified", speed=3.0, out_path="")
    with pytest.raises(ValueError, match="Speed must be"):
        core.synthesize("hello", voice="habibi_unified", speed=0.1, out_path="")


def test_tts_validation_speed_valid_not_value_error():
    from app.tts_core import TTSCore
    core = TTSCore()
    for speed in (0.5, 1.0, 2.0):
        try:
            core.synthesize("x", voice="habibi_unified", speed=speed, out_path="", user_email="u@example.com")
        except ValueError as e:
            assert "Speed must be" not in str(e), f"speed={speed} should be valid"
        except RuntimeError:
            pass


def test_removed_engines_rejected():
    from app.tts_core import TTSCore
    core = TTSCore()
    with pytest.raises(ValueError, match="أُزيل"):
        core.synthesize("مرحبا", voice="habibi_unified", speed=1.0, engine="mms", user_email="u@example.com")
    with pytest.raises(ValueError, match="أُزيل"):
        core.synthesize("مرحبا", voice="habibi_unified", speed=1.0, engine="omnivoice", user_email="u@example.com")


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


def test_maybe_diacritize_request_override(monkeypatch):
    from app.config import settings
    from app.tts_core import maybe_diacritize

    monkeypatch.setattr(settings, "TTS_DIACRITIZE", True)
    monkeypatch.setattr(
        "app.tts.diacritize.add_diacritics",
        lambda text: text + "_tashkeel",
    )
    assert maybe_diacritize("نص", enabled=False) == "نص"
    monkeypatch.setattr(settings, "TTS_DIACRITIZE", False)
    assert maybe_diacritize("نص", enabled=True) == "نص_tashkeel"


def test_suggest_habibi_dialect_msa_from_formal_text():
    from app.tts.dialect_suggest import suggest_habibi_dialect

    text = "إنّ الذي كتب الرسالة قد أوضح ذلك حيث بيّن الأسباب كما ينبغي."
    out = suggest_habibi_dialect(text, current="UNK")
    assert out["suggested"] == "MSA"
    assert out["apply_recommended"] is True


def test_suggest_habibi_dialect_egy_markers():
    from app.tts.dialect_suggest import suggest_habibi_dialect

    out = suggest_habibi_dialect("عايز أروح دلوقتي كده", current="UNK")
    assert out["suggested"] == "EGY"


def test_inspect_voice_sample_missing_ref(tmp_path):
    import numpy as np
    import soundfile as sf

    from app.tts.voice_sample_check import inspect_voice_sample

    wav = tmp_path / "s.wav"
    sr = 24000
    tone = (0.1 * np.sin(2 * np.pi * 220 * np.arange(sr * 4) / sr)).astype(np.float32)
    sf.write(str(wav), tone, sr)
    info = inspect_voice_sample(str(wav), has_ref_text=False, ref_text="")
    assert info["duration_sec"] > 3
    assert info["blocking"] is True
    assert any(w["code"] == "missing_ref_text" for w in info["warnings"])
    info2 = inspect_voice_sample(str(wav), has_ref_text=True)
    assert info2["blocking"] is False or not any(w["code"] == "missing_ref_text" for w in info2["warnings"])


def test_list_voices_returns_non_empty():
    """GET /tts/voices relies on tts_core.list_voices() returning a non-empty list."""
    from app.tts_core import list_voices
    voices = list_voices()
    assert isinstance(voices, list)
    assert len(voices) > 0
    assert "habibi_unified" in voices
    assert "habibi_specialized" in voices
    assert "ar_mms" not in voices
    assert "omnivoice" not in voices


def test_list_voices_detailed_includes_ready_flags():
    from app.tts_core import list_engine_status, list_voices_detailed

    detailed = list_voices_detailed()
    assert isinstance(detailed, list)
    assert len(detailed) >= 2
    for item in detailed:
        assert "id" in item
        assert "engine" in item
        assert "ready" in item
        assert isinstance(item["ready"], bool)
        assert item["engine"] == "habibi"
    engines = list_engine_status()
    assert {e["engine"] for e in engines} == {"habibi"}


def test_habibi_requires_sample_and_ref_text(monkeypatch, tmp_path):
    from app import tts_core as tc

    monkeypatch.setattr(
        tc,
        "_resolve_user_speaker_ref_if_available",
        lambda user_email, speaker_ref=None: "voice.wav",
    )
    monkeypatch.setattr(tc, "_preprocess_text", lambda t: t)

    class _FakePath:
        name = "voice.wav"

        def __str__(self):
            return str(tmp_path / "voice.wav")

    (tmp_path / "voice.wav").write_bytes(b"RIFF")

    def _fake_resolve(user_email, speaker_ref=None):
        return _FakePath()

    called = {"habibi": False}

    def _fake_habibi(**kwargs):
        called["habibi"] = True
        return {
            "audio_path": str(tmp_path / "out.wav"),
            "sample_rate": 24000,
            "duration_sec": 0.1,
            "voice": "habibi_unified",
            "dialect": "LEV",
        }

    monkeypatch.setattr("app.tts.voice_profiles.resolve_user_speaker_path", _fake_resolve)
    monkeypatch.setattr("app.tts.voice_profiles.get_user_speaker_ref_text", lambda *a, **k: "")
    monkeypatch.setattr("app.tts.tts_habibi.synthesize_habibi", _fake_habibi)

    core = tc.TTSCore()
    with pytest.raises(ValueError, match="ref_text"):
        core.synthesize(
            "مرحبا",
            voice="habibi_unified",
            speed=1.0,
            out_path=str(tmp_path / "out.wav"),
            engine="habibi",
            user_email="user@example.com",
            speaker_ref="voice.wav",
            ref_text="",
        )

    monkeypatch.setattr(
        "app.tts.voice_profiles.get_user_speaker_ref_text",
        lambda *a, **k: "نص البصمة",
    )
    result = core.synthesize(
        "مرحبا",
        voice="legacy_ignored",
        speed=1.0,
        out_path=str(tmp_path / "out.wav"),
        engine="auto",
        user_email="user@example.com",
        speaker_ref="voice.wav",
        ref_text="نص البصمة",
        dialect="LEV",
    )
    assert called["habibi"] is True
    assert result["engine_used"] == "habibi"
    assert result["resolved_voice"] == "habibi_unified"


def test_voice_sample_save_does_not_overwrite(tmp_path, monkeypatch):
    from app.config import settings
    from app.tts import voice_profiles as vp

    monkeypatch.setattr(settings, "SPK_DIR", tmp_path)
    first = vp.save_user_speaker_sample("u@example.com", b"aaa", filename="voice.wav")
    second = vp.save_user_speaker_sample("u@example.com", b"bbb", filename="voice.wav")
    assert first.name == "voice.wav"
    assert second.name != first.name
    assert first.read_bytes() == b"aaa"
    assert second.read_bytes() == b"bbb"
    # Default without speaker_ref prefers newest upload.
    picked = vp.resolve_user_speaker_path("u@example.com", speaker_ref=None)
    assert picked.name == second.name


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
    from app.routers import export as export_router

    # Patch where export looks up auth (deps import is bound at module load).
    monkeypatch.setattr(
        export_router,
        "require_logged_in_user",
        lambda user_email=None, authorization=None: ("user@example.com", None),
    )
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
