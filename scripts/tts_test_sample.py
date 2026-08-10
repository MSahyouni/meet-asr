#!/usr/bin/env python3
"""Quick Habibi TTS smoke — requires auth + uploaded voice sample + ref_text."""
import os
import sys

import requests

BASE = os.getenv("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
token = os.getenv("API_TOKEN") or os.getenv("JWT") or ""
email = os.getenv("TTS_USER_EMAIL", "").strip()
ref_text = os.getenv("TTS_REF_TEXT", "").strip()
speaker_ref = os.getenv("TTS_SPEAKER_REF", "").strip()
text = os.getenv("TTS_TEXT", "مرحبا، هذا اختبار لتوليد الصوت بمحرك حبيبي.")

if not token or not email or not ref_text:
    print(
        "Set API_TOKEN (or JWT), TTS_USER_EMAIL, TTS_REF_TEXT"
        " (and optionally TTS_SPEAKER_REF, TTS_TEXT).",
        file=sys.stderr,
    )
    sys.exit(2)

headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
body = {
    "text": text,
    "voice": "habibi_unified",
    "engine": "habibi",
    "speed": 1.0,
    "user_email": email,
    "ref_text": ref_text,
}
if speaker_ref:
    body["speaker_ref"] = speaker_ref

r = requests.post(f"{BASE}/tts", json=body, headers=headers, timeout=1800)
print(r.status_code, r.text[:500])
r.raise_for_status()
