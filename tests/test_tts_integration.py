# tests/test_tts_integration.py — Habibi TTS (needs auth + voice sample + ref_text)
import os
import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_TTS_INTEGRATION", "").lower() not in ("1", "true", "yes"),
    reason="Set RUN_TTS_INTEGRATION=1 with Habibi sample fixtures to run",
)


def test_tts_habibi_only_contract():
    """Placeholder contract: Habibi is the only engine; live call needs sample+ref_text."""
    from app.tts_core import TTS_ALLOWED_ENGINES, TTS_KNOWN_VOICES, TTS_REMOVED_ENGINES

    assert TTS_ALLOWED_ENGINES == {"auto", "habibi"}
    assert "habibi_unified" in TTS_KNOWN_VOICES
    assert "mms" in TTS_REMOVED_ENGINES
    assert "omnivoice" in TTS_REMOVED_ENGINES
