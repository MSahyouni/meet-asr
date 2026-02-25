# Meet-ASR

[![Python CI](https://github.com/MSahyouni/meet-asr/actions/workflows/python-ci.yml/badge.svg?branch=main)](https://github.com/MSahyouni/meet-asr/actions/workflows/python-ci.yml) [![Security Tests](https://github.com/MSahyouni/meet-asr/actions/workflows/security-tests.yml/badge.svg?branch=nabra)](https://github.com/MSahyouni/meet-asr/actions/workflows/security-tests.yml) [![Docker Build](https://github.com/MSahyouni/meet-asr/actions/workflows/docker-test.yml/badge.svg?branch=main)](https://github.com/MSahyouni/meet-asr/actions/workflows/docker-test.yml) [![Docker Publish](https://github.com/MSahyouni/meet-asr/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/MSahyouni/meet-asr/actions/workflows/docker-publish.yml)

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

المشروع مُنظَّم طبقاً للقالب الرسمي:

```
meet-asr/
├── apps/
│   ├── web/              # واجهة Flutter (اختيارية/مستقلة)
│   └── api/              # خادم FastAPI
├── static/
│   └── frontend/         # الواجهة الافتراضية المدمجة مع API (تعمل على /)
├── docker/               # Dockerfile.api
├── scripts/              # سكربتات مساعدة
├── docs/                 # وثائق المشروع
├── docker-compose.yml    # تعريف البنية التحتية (Development)
└── docker-compose.prod.yml # تعريف البنية التحتية (Production)
```

الإصدارات الحالية تستخدم:
- `apps/api/` يحتوي على كود FastAPI (ملفات `api.py` و `app/…`).
- `static/frontend/` هي الواجهة الافتراضية المرتبطة مباشرة مع API.
- `apps/web/` يحتوي تطبيق Flutter ويمكن تشغيله بشكل مستقل إذا رغبت.

**المواقع الرسمية الحالية:**
- بيئة Python الافتراضية: `.venv/` في جذر المشروع.
- بيانات التشغيل والنماذج والمخرجات: `data/` في جذر المشروع (وليس داخل `apps/api/`).



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

**الموقع المعياري (Canonical):**  
المشروع يَستخدِم `.venv/` في جذر المشروع (مُضبَط في `.vscode/settings.json` عند استخدام VS Code). 
إن وُجِدَ `venv/` قديم، تجاهَله (مُخفِي في إعدادات المحرر والبحث).

```bash
python -m venv .venv
source .venv/bin/activate   # Linux / Mac
.venv\Scripts\activate     # Windows
```

pip install -U pip
pip install -r apps/api/requirements.txt

TTS عربي: ar_mms (أوفلاين مع transformers، مع خيار seed لتغيير الإيقاع). لأربعة أصوات إضافية: pip install git+https://github.com/nipponjo/tts_arabic.git ثم استخدم ar_1, ar_2, ar_3, ar_4.


---

3) إعداد متغيرات البيئة (اختياري)

انسخ القالب وعدّل القيم:

```bash
cp apps/api/.env.example apps/api/.env
```

أو على Windows (PowerShell):

```powershell
Copy-Item apps/api/.env.example apps/api/.env
```

**ملاحظة مهمة:** النماذج المحملة مسبقاً في `data/models/` ستُستخدم تلقائياً. 
- `HF_HOME` تُضبط تلقائياً على `data/models/` بحيث لا تُحمّل النماذج من الإنترنت
- `SENTENCE_TRANSFORMERS_HOME` تُضبط على `data/models/`
- إذا أضفت نموذجاً جديداً، ضعه مباشرة في `data/models/{model-name}/`

المتغيرات الأساسية في `.env`:
- `HF_TOKEN` — مفتاح Hugging Face (للنماذج الخاصة فقط)
- `WHISPER_MODEL` — heavy (large-v3) - افتراضي وثابت
- `ASR_DATA_DIR` — مجلد البيانات (افتراضي: `data`)
- `ASR_ENV` — بيئة التشغيل (`development` أو `production`)
- `WHISPER_DEVICE` — cuda أو cpu
- `JWT_SECRET` — مفتاح توقيع JWT محلي (أوفلاين)
- `JWT_EXPIRES_SECONDS` — مدة صلاحية التوكن بالثواني (افتراضي 86400)
- `JWT_ISSUER` — قيمة `iss` داخل JWT (افتراضي: `meet-asr`)
- `JWT_AUDIENCE` — قيمة `aud` داخل JWT (افتراضي: `meet-asr-api`)
- `ADMIN_EMAILS` — قائمة إيميلات الأدمن مفصولة بفواصل (مثال: `admin@local,owner@local`)

**ملاحظة إنتاجية مهمة (CORS/JWT):**
- في بيئة `production` يجب تعيين `JWT_SECRET` بقيمة قوية، واستخدام `ASR_ALLOWED_ORIGINS` بقيم صريحة (بدون `*`).

**التخزين المحلي الدائم (Offline Persistence):**
- يتم حفظ بيانات المستخدمين والأنشطة في SQLite محلي: `data/meetasr.sqlite3`
- لا حاجة لأي قاعدة بيانات سحابية، ويستمر العمل بالكامل أوفلاين


---

▶️ تشغيل API

**ملاحظة:** جميع وحدات التطبيق (`app/config.py`, `app/tts_core.py`، إلخ) موجودة تحت `apps/api/app/`،  
لذا يجب ضمان أن مسار الاستيراد صحيح عند بدء الخادم.

**الطريقة الموصى بها:**

```powershell
# من جذر المشروع
cd apps/api
uvicorn api:app --host 0.0.0.0 --port 8000
```

**بدائل:**

```powershell
# من جذر المشروع مباشرة (بدون cd)
uvicorn api:app --app-dir apps/api --host 0.0.0.0 --port 8000
```

بعد التشغيل الناجح ستظهر رسالة `INFO: Application startup complete.`


تحقق من الصحة: http://127.0.0.1:8000/health

الواجهة متوفرة على: http://127.0.0.1:8000/


---

⚡ التشغيل على GPU (بدون Docker)

تأكد من تثبيت CUDA وتعريفات NVIDIA.

تحقق: python -c "import torch; print(torch.cuda.is_available())"


---

🐳 التشغيل عبر Docker

Development

docker compose -f docker-compose.yml up -d --build

Production + GPU

docker compose -f docker-compose.prod.yml up -d --build


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

**ميزات المنصة الجديدة:**
- **POST /auth/register** — تسجيل مستخدم
- **POST /auth/login** — تسجيل دخول
- **GET /users/me** — جلب الملف الشخصي الحالي عبر Bearer token
- **PUT /users/me** — تحديث الملف الشخصي الحالي عبر Bearer token
- **GET /users/profile/{email}** — الملف الشخصي
- **PUT /users/profile/{email}** — تحديث الملف الشخصي
- **GET /dashboard/my-summary** — ملخص لوحة المستخدم الحالي عبر Bearer token
- **GET /dashboard/my-activities** — نشاطات المستخدم الحالي عبر Bearer token
- **GET /dashboard/my-usage** — استخدام API للمستخدم الحالي عبر Bearer token
- **GET /dashboard/my-usage-chart** — بيانات الرسم البياني للمستخدم الحالي عبر Bearer token
- **GET /dashboard/summary/{user_email}** — ملخص لوحة التحكم
- **GET /dashboard/overview** — نظرة عامة للإحصائيات

**ملاحظة توافق مهمة:**
- `POST /summarize` يقبل الآن **FormData** و **JSON** (مفيد لتطبيق Flutter والواجهة الافتراضية معًا)
- endpoints القديمة التي تعتمد `{email}` أو `{user_email}` أصبحت محمية: الوصول مسموح فقط لصاحب الحساب أو Admin عبر Bearer token.

**ملاحظة اختبار (Security Coverage):**
- يوجد تغطية اختبارية للمسارات الآمنة `/users/me` و`/dashboard/my-summary` و`/dashboard/my-activities` و`/dashboard/my-usage` و`/dashboard/my-usage-chart` داخل `tests/test_secure_endpoints.py`.

---

### أمثلة cURL

**التفريغ (رفع ملف):**
```bash
curl -X POST http://localhost:8000/transcribe \
  -F "file=@/path/to/audio.wav" \
  -F "user_email=user@example.com" \
  -F "enhance_mode=off" \
  -F "diarize=true" \
  -F "async_mode=false"
```

**تحويل النص إلى كلام (TTS):**
```bash
curl -X POST http://localhost:8000/tts \
  -H "Content-Type: application/json" \
  -d '{"text":"مرحبا هذا اختبار","voice":"af_heart","speed":1.0,"format":"wav","user_email":"user@example.com"}'
```
الاستجابة تتضمن `download_url` لتحميل ملف WAV.

ملاحظة: `user_email` اختياري، لكنه يفعّل تسجيل النشاطات في لوحة التحكم (ASR/TTS/NLP).

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

📚 نماذج محلية وتخزين مؤقت (Local Model Caching)

يدعم المشروع استخدام النماذج المحملة محليا في `data/models/` لتجنب اعادة التحميل من الانترنت.

**النماذج المدعومة محليا:**

```
data/models/
├── whisper-large-v3/              # نموذج Whisper المستخدم (heavy = large-v3)
├── multilingual-e5-base/          # نموذج التضمين متعدد اللغات
├── spkrec_ecapa_cpu/              # نموذج تمييز المتحدثين
├── summarizers/
│   └── mT5_XLSum/                 # نموذج التلخيص
└── ultra/                         # نماذج اضافية
```

**كيفية التشغيل:**

1. تُحمّل النماذج تلقائيا من `data/models/` ان وجدت
2. لا تُعاد تحميل من الانترنت (يستثنى NER و Punct اذا لم تُوجد محليا)
3. متغيرات البيئة تُضبط تلقائيا:
  - `HF_HOME=data/models` (مكان تخزين النماذج)
  - `SENTENCE_TRANSFORMERS_HOME=data/models`

**لتجنب تحميل النماذج من الانترنت:**

```python
# في config.py، كل نموذج يفحص المسار المحلي اولا:
_prefer_local(path: pathlib.Path, fallback_hf_id: str) -> str
```

اذا كنت تريد اضافة نموذج جديد:
1. حمّله من Hugging Face يدويا او عبر `huggingface_hub.snapshot_download()`
2. ضعه في `data/models/{model-name}/`
3. عدّل المسار في `config.py` اذا لزم الامر



---

📦 Docker Images (GitHub Packages)

ghcr.io/<username>/meetasr-api:latest


---

📄 الترخيص

MIT License
