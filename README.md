Meet-ASR

Meet-ASR هو نظام تفريغ صوتي (Speech-to-Text) احترافي يدعم تمييز المتحدثين (Speaker Diarization) وتلخيص النص، مع تحسين جودة الصوت (Enhance) قبل المعالجة، ومصمم ليعمل كخدمة مستقلة قابلة للدمج في أي تطبيق.

المشروع مهيأ للاستخدام البحثي والمؤسسي، ويعمل محليًا أو عبر Docker، مع دعم CPU و GPU.


---

✨ الميزات

🎙️ تفريغ صوتي عالي الدقة باستخدام Whisper

🧑‍🤝‍🧑 تمييز المتحدثين (Speaker Diarization)

🔊 تحسين جودة الصوت (Enhance)

تقليل الضجيج

تحسين وضوح الصوت البشري

إعادة أخذ العينات تلقائيًا


📝 تلخيص النص الناتج

🌐 واجهة برمجية REST (API)

🖥️ واجهة ويب (HTML/JS)

⚡ دعم التشغيل على CPU أو GPU

🐳 دعم Docker و Docker Compose

📦 نشر تلقائي على GitHub Container Registry

🔊 TTS (تحويل النص إلى صوت): Kokoro للإنجليزية + MMS-TTS للعربية (أوفلاين)



---

🧠 كيف يعمل

يعتمد Meet-ASR على فصل واضح بين الواجهة والمعالجة:

API

Enhance → ASR → Diarization → Summarize


Web UI

واجهة استخدام تتواصل مع الـ API فقط


يمكن لأي تطبيق خارجي استخدام الـ API مباشرة


> الواجهة تعمل مباشرة من API على المسار / — لا حاجة لخادم منفصل.




---

🗂️ بنية المشروع

**نقاط الدخول:** `api.py` (خادم API + واجهة ويب) · `config.py`

**الحزم:** `asr/` (تفريغ صوت) · `nlp/` (تلخيص، NER، RAG) · `routers/` (مسارات API) · `static/frontend/` (واجهة HTML/JS)

تفاصيل الهيكل والتبعيات: [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md)

```
docker/            — Dockerfile.api, docker-compose, docker-compose.prod
.github/workflows/ — docker-test.yml, docker-publish.yml, python-ci.yml
scripts/           — إعداد RAG، اختبارات TTS
tools/             — تحميل وفهرسة ArabicText
tests/             — smoke_test، test_api_units، test_tts_integration
static/frontend/   — واجهة HTML/JS
flutter_app/       — تطبيق Flutter (عميل اختياري)
```


---

⚙️ المتطلبات

بدون Docker

Python 3.10 أو أحدث

FFmpeg

(اختياري) NVIDIA GPU


مع Docker

Docker 24 أو أحدث

Docker Compose

(اختياري) NVIDIA Container Toolkit



---

🚀 التشغيل بدون Docker (محليًا)

1) تثبيت FFmpeg

على Ubuntu / Debian: sudo apt-get update
sudo apt-get install -y ffmpeg

على Windows:

تثبيت FFmpeg وإضافة مساره إلى PATH



---

2) إنشاء بيئة Python

python -m venv .venv
source .venv/bin/activate   (Linux / Mac)
.venv\Scripts\activate     (Windows)

pip install -U pip
pip install -r requirements.txt

TTS عربي: ar_mms (أوفلاين مع transformers، مع خيار seed لتغيير الإيقاع). لأربعة أصوات إضافية: pip install git+https://github.com/nipponjo/tts_arabic.git ثم استخدم ar_1, ar_2, ar_3, ar_4.


---

3) إعداد متغيرات البيئة (اختياري)

انسخ القالب وعدّل القيم:

```bash
cp .env.example .env
```

المتغيرات الأساسية في `.env`:
- `HF_TOKEN` — مفتاح Hugging Face (للنماذج الخاصة)
- `WHISPER_MODEL` — light | medium | large-v3
- `ASR_DATA_DIR` — مجلد البيانات (افتراضي: `data`)


---

▶️ تشغيل API

uvicorn api:app --host 0.0.0.0 --port 8000

تحقق من الصحة: http://127.0.0.1:8000/health

الواجهة متوفرة على: http://127.0.0.1:8000/


---

⚡ التشغيل على GPU (بدون Docker)

تأكد من تثبيت CUDA وتعريفات NVIDIA.

تحقق: python -c "import torch; print(torch.cuda.is_available())"


---

🐳 التشغيل عبر Docker

Development

docker compose -f docker/docker-compose.yml up -d --build

Production + GPU

docker compose -f docker/docker-compose.prod.yml up -d --build


---

🔌 نقاط النهاية (API)

- **GET /health** — حالة الخادم (asr، diarization، tts، ffmpeg)
- **POST /transcribe** — تفريغ ملف صوتي واحد
- **POST /transcribe-batch** — تفريغ عدة ملفات
- **GET /tts/voices** — قائمة أصوات TTS المتاحة
- **POST /tts** — تحويل نص إلى كلام (حد 5000 حرف، 12 طلب/دقيقة)
- **POST /summarize** — تلخيص نص
- **POST /enroll-speaker** — تسجيل بصمة متحدث
- **GET /enrolled-speakers** — قائمة المتحدثين المسجلين
- **GET /download?path=...** — تحميل ملف من مجلد المخرجات

---

### أمثلة cURL

**التفريغ (رفع ملف):**
```bash
curl -X POST http://localhost:8000/transcribe \
  -F "file=@/path/to/audio.wav" \
  -F "enhance_mode=off" \
  -F "diarize=true" \
  -F "async_mode=false"
```

**تحويل النص إلى كلام (TTS):**
```bash
curl -X POST http://localhost:8000/tts \
  -H "Content-Type: application/json" \
  -d '{"text":"مرحبا هذا اختبار","voice":"af_heart","speed":1.0,"format":"wav"}'
```
الاستجابة تتضمن `download_url` لتحميل ملف WAV.

---

### تحسين الصوت (enhance_mode)

معامل **enhance_mode** يتحكم بمرحلة تحسين الصوت قبل التفريغ:

| القيمة | الوصف |
|--------|--------|
| **off** | بدون تحسين (افتراضي، الأسرع) |
| **light** | تطبيع + فلتر highpass فقط (سريع، بدون تقليل ضجيج) |
| **full** | تحسين كامل: تقليل ضجيج + فلاتر (أنسب للملفات ذات الضجيج) |

يمكن أيضاً إرسال **enhance=true** (توافق قديم) ويُعادل **enhance_mode=full**.


---

🎯 حالات الاستخدام

تفريغ الاجتماعات

المقابلات الصحفية

المحاضرات والدروس

الأرشفة الصوتية

أدوات البحث والتحليل



---

📦 Docker Images (GitHub Packages)

ghcr.io/<username>/meetasr-api:latest


---

📄 الترخيص

MIT License
