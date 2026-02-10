#!/usr/bin/env python
# scripts/test_tts_asr_live.py — فحص جودة TTS العربي ومسار ASR
"""
تشغيل: python scripts/test_tts_asr_live.py
يتطلب: API يعمل على http://127.0.0.1:8000
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import requests

BASE = os.getenv("ASR_API_BASE", "http://127.0.0.1:8000")
API_KEY = os.getenv("API_TOKEN", "")


def test_health():
    """التحقق من صحة الـ API."""
    r = requests.get(f"{BASE}/health", timeout=5)
    r.raise_for_status()
    print("✓ API يعمل:", r.json())
    return True


def test_tts_arabic():
    """اختبار TTS بالنص العربي."""
    samples = [
        "مرحبا بك في نظام نَبْرَة.",
        "الجمهورية العربية السورية.",
        "واحد اثنان ثلاثة أربعة خمسة.",
    ]

    headers = {}
    if API_KEY:
        headers["X-API-Key"] = API_KEY

    for i, text in enumerate(samples):
        try:
            r = requests.post(
                f"{BASE}/tts",
                json={"text": text, "voice": "af_heart", "speed": 1.0},
                headers=headers,
                timeout=60,
            )
            r.raise_for_status()
            data = r.json()
            audio_path = data.get("audio_path", "")
            duration = data.get("duration_sec", 0)
            job_id = data.get("job_id", "")

            if audio_path and Path(audio_path).exists():
                print(f"  ✓ TTS #{i+1}: «{text[:50]}» → {duration:.2f}s, job_id={job_id}")
            else:
                print(f"  ✓ TTS #{i+1}: «{text[:40]}» → duration={duration}s (path: {audio_path})")
        except Exception as e:
            print(f"  ✗ TTS #{i+1} فشل: {e}")
            return False

    print("✓ اختبار TTS العربي مكتمل.")
    return True


def test_asr(audio_path: Path = None):
    """اختبار ASR — رفع ملف صوتي."""
    if not audio_path or not audio_path.exists():
        # استخدام مخرجات TTS إن وجدت
        candidates = list((ROOT / "data" / "outputs" / "tts").glob("*.wav")) if (ROOT / "data" / "outputs" / "tts").exists() else []
        if not candidates:
            candidates = []
        if not candidates:
            print("  ⚠ لا يوجد ملف صوتي للاختبار. نفّذ test_tts أولاً أو مرّر مسار ملف.")
            return False
        audio_path = candidates[-1]

    headers = {}
    if API_KEY:
        headers["X-API-Key"] = API_KEY

    try:
        with open(audio_path, "rb") as f:
            r = requests.post(
                f"{BASE}/transcribe",
                files={"file": (audio_path.name, f, "audio/wav")},
                data={
                    "model_name": "light",
                    "enhance_mode": "off",
                    "diarize": "false",
                    "punctuate": "false",
                },
                headers=headers,
                timeout=120,
            )
        r.raise_for_status()
        data = r.json()
        text = data.get("text", "")
        job_id = data.get("job_id", "")
        timings = data.get("timings_ms", {})

        print(f"  ✓ ASR: النص المستخرج ({len(text)} حرف)")
        print(f"    └─ {text[:200]}..." if len(text) > 200 else f"    └─ {text}")
        if timings:
            print(f"    └─ timings_ms: {timings}")
        if job_id:
            print(f"    └─ job_id: {job_id}")
        return True
    except Exception as e:
        print(f"  ✗ ASR فشل: {e}")
        return False


def main():
    print("=== فحص جودة TTS العربي ومسار ASR ===\n")
    if not test_health():
        sys.exit(1)
    print()
    print("--- TTS (نص عربي → صوت) ---")
    test_tts_arabic()
    print()
    print("--- ASR (صوت → نص) ---")
    test_asr()
    print("\n=== انتهى الاختبار ===")


if __name__ == "__main__":
    main()
