# tests/test_tts_integration.py — integration test for POST /tts (skipped by default in CI)
import os
import pytest

# Skip unless explicitly requested (e.g. RUN_TTS_INTEGRATION=1)
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_TTS_INTEGRATION", "").lower() not in ("1", "true", "yes"),
    reason="Set RUN_TTS_INTEGRATION=1 to run TTS integration test",
)


def test_tts_returns_ok_and_downloadable():
    """Call POST /tts with small text; expect ok=True and a downloadable path."""
    from fastapi.testclient import TestClient
    from api import app

    client = TestClient(app)
    resp = client.post(
        "/tts",
        json={"text": "Test.", "voice": "af_heart", "speed": 1.0, "format": "wav"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data.get("ok") is True
    assert "audio_path" in data
    assert "download_url" in data
    assert "duration_sec" in data
    assert "sample_rate" in data
    # Optional: GET download_url and check 200 (if path is absolute, client may need base_url)
    path = data.get("audio_path")
    if path and os.path.isfile(path):
        assert path.endswith(".wav")
