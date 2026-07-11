#!/usr/bin/env python
# تشغيل: python scripts/tts_test_sample.py
# يتطلب: API على http://127.0.0.1:8000
import requests

text = """السلام عليكم ورحمة الله وبركاته. نبدأ معكم اليوم ببداية جديدة من هذا التطبيق الذي يستطيع أن يميز بين الأصوات وبإذن الله توكلنا على الله."""

r = requests.post(
    "http://127.0.0.1:8000/tts",
    json={"text": text, "voice": "ar_mms", "speed": 1.0},
    timeout=180,
)
r.raise_for_status()
data = r.json()
path = data.get("audio_path", "")
dur = data.get("duration_sec", 0)
job = data.get("job_id", "")
dl = data.get("download_url", "")

print("✓ تم التوليد بنجاح")
print("  المدة:", dur, "ثانية")
print("  job_id:", job)
print("  الملف:", path)
if dl:
    print("  رابط التحميل:", dl)
