# Meet-ASR (نَبْرَة)

منصة محلية (Offline-first) للاستماع والتحويل والتلخيص وتوليد الصوت، مبنية على FastAPI مع واجهة ويب مدمجة.

- ASR: تفريغ صوتي + تمييز متحدثين.
- NLP: تلخيص + كلمات مفتاحية + NER.
- TTS: MMS عربي + Habibi + OmniVoice (استنساخ بصمة عربي + لهجات).
- Auth + Users + Dashboard + Billing.
- تشغيل محلي أو Docker، مع دعم CPU/GPU.

---

## 1) نظرة معمارية سريعة

- نقطة التشغيل الأساسية: `apps/api/app/main.py`.
- `apps/api/api.py` غلاف توافق فقط لتشغيل قديم (`uvicorn api:app`).
- التطبيق الرئيسي: `apps/api/app/main.py`.
- الواجهة الأساسية الحالية: `static/frontend/` وتُخدَّم على `/`.
- واجهة Flutter في `nabra/` اختيارية/بديلة وليست المسار التشغيلي الافتراضي.
- البيانات المحلية: `data/` (نماذج، مخرجات، أصوات، SQLite).

ملاحظة مهمة:
- المسارات **الرسمية** للواجهة والتكامل الجديد: `/asr/*`, `/nlp/*`, `/tts/*`.
- توجد مسارات **legacy** للتوافق الخلفي عبر `app/compat` (مثل `/transcribe`, `/summarize`, `/tts`).

### مسارات API الرسمية (Canonical)

| الميزة | المسار | ملاحظة |
|--------|--------|--------|
| **ASR** | `POST /asr/transcribe` | رفع ملف أو تسجيل مباشر |
| | `GET /asr/job/{id}` | متابعة الوظيفة |
| | `GET /asr/download` | تحميل مخرجات (مسار آمن تحت `data/outputs`) |
| | `POST /asr/enroll-speaker` | تسجيل متحدث |
| | `GET /asr/enrolled-speakers` | قائمة المتحدثين |
| **NLP** | `POST /nlp/summarize` | تلخيص (FormData أو JSON) |
| | `POST /nlp/ner` | استخراج كيانات |
| **TTS** | `POST /tts` | توليد صوت WAV |
| | `GET /tts/voices` | قائمة الأصوات |
| | `POST /tts/voice-samples` | رفع بصمات المستخدم |
| | `GET /tts/voice-samples` | قائمة بصمات المستخدم |
| **صحة** | `GET /health` | فحص الخدمة والنماذج |

> التفاصيل الكاملة: `http://127.0.0.1:8000/docs`

---

## 2) بنية المشروع

```text
meet-asr/
├─ apps/
│  └─ api/                    # FastAPI backend (main.py, routers, features)
├─ static/frontend/           # واجهة HTML/CSS/JS المدمجة
├─ scripts/                   # سكربتات (OmniVoice، Docker، setup_env، migrate_to_dot_venv)
├─ tests/                     # pytest (unit + integration markers)
├─ docker/                    # Dockerfile.api
├─ nabra/                     # Flutter app (اختياري)
├─ data/                      # نماذج، مخرجات، أصوات، SQLite (gitignored)
├─ .tools/                    # أدوات منفصلة (OmniVoice inference venv)
├─ .github/workflows/         # CI (ci.yml — unit + security + integration)
├─ .venv/                     # بيئة Python المفضّلة (أنشئها عبر run.sh أو migrate)
├─ README.md
├─ LICENSE
├─ pytest.ini
├─ .env.example               # قالب Docker/Compose (جذر)
├─ docker-compose.yml
├─ docker-compose.prod.yml
├─ run.sh                     # تشغيل Linux/WSL
├─ run.ps1 / run.bat          # تشغيل Windows
└─ venv/                      # بيئة قديمة (يُفضَّل الترحيل إلى .venv)
```

---

## 3) المتطلبات

### تشغيل محلي
- Python 3.10+
- FFmpeg
- (اختياري) CUDA/GPU

### Docker
- Docker + Docker Compose
- (اختياري) NVIDIA Container Toolkit

---

## 4) تشغيل سريع (Windows)

### الأسهل
```powershell
.\run.ps1
```
أو بالنقر المزدوج:
```bat
run.bat
```

ما يفعله `run.ps1`:
- يفضّل `.venv`، وإذا وجد `venv` القديم يستخدمه تلقائيًا.
- ينشئ `.venv` عند عدم وجود أي بيئة افتراضية.
- يشغّل `uvicorn` من `apps/api`.
- يفتح المتصفح تلقائيًا عند جاهزية المنفذ `8000`.

> السكربت يثبّت المتطلبات تلقائيًا عند تغيّر `requirements.txt`.

### Linux
```bash
chmod +x ./run.sh
./run.sh
```

مع تخصيص المنفذ أو المضيف:
```bash
PORT=9000 HOST=0.0.0.0 ./run.sh
```

ما يفعله `run.sh`:
- يستخدم `.venv` إن وجدت، وإلا يستخدم `venv` القديم.
- ينشئ `.venv` تلقائيًا عند عدم وجود بيئة افتراضية.
- يثبت المتطلبات من `apps/api/requirements.txt` عند تغيرها.
- يشغّل `uvicorn` باستخدام Python من داخل البيئة الافتراضية.
- يدعم `PORT` و `HOST` من متغيرات البيئة مع القيم الافتراضية `8000` و `127.0.0.1`.

### التشغيل اليدوي
```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -U pip
pip install -r apps/api/requirements.txt

# اختياري: Habibi + mishkal (OmniVoice عبر سكربت منفصل)
# ./.venv/bin/pip install -r apps/api/requirements-optional.txt

cd apps/api
python -m uvicorn api:app --host 0.0.0.0 --port 8000
```

### حزم اختيارية (TTS extras)
الـ API الأساسي (Whisper / MMS / تلخيص) يعمل بعد `requirements.txt` فقط. الميزات التالية **اختيارية** ولن تُثبَّت تلقائيًا:

| الميزة | التثبيت | ملاحظة |
|--------|---------|--------|
| **mishkal** | `./.venv/bin/pip install mishkal` ثم `TTS_DIACRITIZE=1` | تشكيل عربي قبل TTS |
| **Habibi** | `./.venv/bin/pip install habibi-tts` | لهجات + يحتاج عينة صوت و`ref_text` |
| **OmniVoice** | `./scripts/download_omnivoice.sh` + venv تحت `.tools/omnivoice/` | بيئة منفصلة عن API (~3.2 GB) |

ملف مجمّع: `apps/api/requirements-optional.txt` (بدون OmniVoice — يبقى في `.tools/`).

### التشغيل اليدوي على Linux
```bash
cd /path/to/meet-asr
source venv/bin/activate
cd apps/api
python -m uvicorn api:app --host 0.0.0.0 --port 8000
```

إذا كانت البيئة الافتراضية باسم `.venv`:
```bash
cd /path/to/meet-asr
source .venv/bin/activate
cd apps/api
python -m uvicorn api:app --host 0.0.0.0 --port 8000
```

روابط مفيدة بعد التشغيل:
- الواجهة: `http://127.0.0.1:8000/`
- الصحة: `http://127.0.0.1:8000/health`
- OpenAPI: `http://127.0.0.1:8000/docs`

---

## 5) إعداد البيئة

القوالب:
- `apps/api/.env.example` للتشغيل المحلي من داخل `apps/api`.
- `.env.example` في الجذر لتشغيل Docker/Compose من الجذر.

للتشغيل المحلي (داخل Python app):
```powershell
Copy-Item apps/api/.env.example apps/api/.env
```

أو توليد إعدادات تطوير جاهزة (يكتشف CUDA وmishkal وOmniVoice تلقائيًا):
```bash
chmod +x scripts/setup_env.sh
./scripts/setup_env.sh          # لا يستبدل ملفات موجودة
./scripts/setup_env.sh --force  # إعادة توليد JWT_SECRET والقيم
```

أهم المتغيرات:
- `ASR_ENV`, `ASR_ALLOWED_ORIGINS`
- `JWT_SECRET`, `JWT_EXPIRES_SECONDS`, `JWT_ISSUER`, `JWT_AUDIENCE`, `ADMIN_EMAILS`
- `WHISPER_MODEL`, `WHISPER_DEVICE`, `WHISPER_COMPUTE`
- `TTS_MMS_ENABLED`, `TTS_PREPROCESS_ENABLED`, `TTS_DIACRITIZE`
- `OMNIVOICE_TIMEOUT_SEC`, `OMNIVOICE_INFER_BIN`
- `RAG_ENABLE`, `RAG_EMB_MODEL`

ملاحظات:
- التطبيق يحمّل `.env` من `apps/api/.env` محليًا.
- في Docker، ملف `docker-compose*.yml` يمرر `.env` من جذر المشروع إلى الحاوية.
- عند تغيير إعدادات جوهرية، حدّث القالبين معًا (`apps/api/.env.example` و`.env.example` في الجذر).
- **البيئة الافتراضية:** يُفضَّل `.venv/`. إن كان لديك `venv/` قديم:
  ```bash
  chmod +x scripts/migrate_to_dot_venv.sh
  ./scripts/migrate_to_dot_venv.sh
  ```

---

## 6) Docker

### Development
```powershell
docker compose -f docker-compose.yml up -d --build
```

### Production
```powershell
docker compose -f docker-compose.prod.yml up -d --build
```

**ملاحظات تشغيل على الخادم (إنتاج):**
- يستخدم ملف الإنتاج ربطًا مباشرًا للمجلد `./data` داخل الحاوية (`/app/data`) لضمان حفظ النماذج والمخرجات.
- تم ضبط `shm_size` و `ulimits` في ملف الإنتاج لتحسين الاستقرار مع أحمال الذكاء الاصطناعي.
- أول تشغيل يمكن أن يكون أبطأ بسبب تنزيل النماذج المطلوبة.
- بعد اكتمال تنزيل نموذج `ultra` بنجاح، يمكن قفل الأوفلاين بتغيير `ULTRA_ALLOW_DOWNLOAD=0` في `.env` ثم إعادة تشغيل الخدمة.

### سكربت مختصر
```powershell
powershell -ExecutionPolicy Bypass -File scripts/docker.ps1 -Action up -Env dev
powershell -ExecutionPolicy Bypass -File scripts/docker.ps1 -Action logs -Env dev
powershell -ExecutionPolicy Bypass -File scripts/docker.ps1 -Action down -Env dev
```

- `-Env prod` لاستخدام ملف الإنتاج.
- الأفعال المدعومة: `up`, `down`, `logs`, `ps`, `restart`, `pull`.

---

## 7) القدرات الأساسية

### ASR
- `POST /transcribe` (legacy)
- `POST /asr/transcribe` (feature route)
- `POST /transcribe-batch` / `POST /asr/transcribe-batch` (alias للتوافق الخلفي؛ نفس منطق ودالة `transcribe`)
- نفس endpoint يدعم رفع `file` أو `audio` أو `files` (ملف واحد أو عدة ملفات).
- دعم `enhance_mode` (`off`, `light`, `full`) و async jobs.

### NLP
- `POST /summarize` / `POST /nlp/summarize`
- `POST /ner` / `POST /nlp/ner`
- التلخيص يعتمد دالة endpoint واحدة (`summarize_after`) وتُعرَض عبر المسارين للتوافق والتنظيم.
- `summarize` يقبل FormData و JSON.
- الوضع الافتراضي للتلخيص أصبح `ultra` لأعلى جودة عربية.
- عند أول طلب `ultra` يتم تنزيل النموذج إلى `data/models/summarizers/ultra/` ثم الاعتماد عليه محليًا.

### TTS
- `POST /tts` (تحويل نص إلى WAV)
- `GET /tts/voices`
- وضع `engine=auto` يعطي أولوية لـ **OmniVoice** عند وجود بصمة للمستخدم (لا يحتاج `ref_text`)، ثم **Habibi** عند توفر `ref_text`، ثم fallback تلقائي إلى MMS عربي.

#### OmniVoice (استنساخ بصمة ~3.2 GB)
- `engine=omnivoice` — استنساخ صوت بدون `ref_text` (اختياري لتحسين الجودة).
- يُشغَّل كأداة CLI داخل بيئة منفصلة لتفادي تعارض المتطلبات مع الـ API.
- **تنزيل النموذج مسبقًا (موصى به):**
  ```bash
  chmod +x scripts/download_omnivoice.sh scripts/cleanup_omnivoice_cache.sh
  ./scripts/download_omnivoice.sh          # ~3.2 GB، قابل للاستئناف
  ./scripts/cleanup_omnivoice_cache.sh     # حذف بقايا .incomplete بعد الاكتمال
  ```
- يستخدم نفس سياسة إعادة المحاولة `download_retry` مثل Whisper/NLP.
- تثبيت أداة الاستنتاج (مرة واحدة):
  ```bash
  python3 -m venv .tools/omnivoice/.venv
  .tools/omnivoice/.venv/bin/pip install -U pip omnivoice
  export OMNIVOICE_INFER_BIN="$PWD/.tools/omnivoice/.venv/bin/omnivoice-infer"
  ```

#### تشكيل عربي قبل TTS (`TTS_DIACRITIZE`)
- يحسّن نطق النصوص العربية **غير المشكّلة** قبل التوليد.
- التفعيل:
  ```bash
  ./.venv/bin/pip install mishkal   # داخل بيئة المشروع — لا تستخدم pip النظام
  # في apps/api/.env:
  TTS_DIACRITIZE=1
  ```
- يُطبَّق على محركات TTS عند التفعيل؛ قد يبطئ التوليد قليلاً.

#### Habibi (لهجات عربية)
- `engine=habibi` (Unified/Specialized لهجات عربية متعددة) ويتطلب:
  - تثبيت اختياري: `./.venv/bin/pip install habibi-tts`
  - `user_email` + عينة صوت مرفوعة مسبقًا
  - `ref_text` (نص مطابق لعينة الصوت المرجعية) — يمكن حفظه مرة واحدة عند رفع العينة عبر `POST /tts/voice-sample`
  - `dialect` اختياري (`UNK|MSA|SAU|UAE|ALG|IRQ|EGY|MAR|OMN|TUN|LEV|SDN|LBY`)
- بصمات المستخدم (Habibi/OmniVoice):
  - `POST /tts/voice-sample`
  - `POST /tts/voice-samples` (يدعم أيضًا `ref_texts_json` كخريطة JSON: اسم_الملف -> ref_text، و`default_ref_text` احتياطي)
  - `GET /tts/voice-samples`
  - `GET /tts/voice-file`
  - `DELETE /tts/voice-sample`
- حفظ بصمات المستخدم في: `data/voices/<sanitized_user_email>/`.

### Auth / Users / Dashboard / Billing
- Auth: `register`, `login`, `logout`, `logout-all`, `sessions/status`, `me/permissions`.
- Users: `/users/me`, إدارة ملف شخصي، وقوائم/إحصائيات بصلاحية admin.
- Dashboard: ملخصات ونشاط واستخدام للمستخدم الحالي أو self/admin.
- Billing: plans/subscription/invoices/payment-methods.

> التفاصيل الدقيقة للمدخلات/المخرجات في `docs` عبر OpenAPI: `/docs`.

---

## 8) الأمان

- JWT مع `iss` و `aud` وتاريخ صلاحية.
- إبطال جلسات server-side عبر `token_version` (مثلاً `logout-all`).
- حماية self/admin لمسارات الحسابات.
- CORS صارم في الإنتاج (ممنوع wildcard عند `ASR_ENV=production`).
- Rate limiting عبر `slowapi` على المسارات الحساسة.

---

## 9) التخزين المحلي والأوفلاين

- قاعدة البيانات: `data/meetasr.sqlite3`
- المخرجات: `data/outputs/`
- النماذج: `data/models/`
- الأصوات: `data/voices/`

يعمل المشروع محليًا بالكامل عند توفر النماذج المطلوبة داخل `data/models`.

---

## 10) اختبارات سريعة

المرجع التشغيلي الحالي للاختبارات: `tests/` في جذر المشروع.

من داخل `apps/api`:
```bash
# اختبارات الوحدة (سريعة — تُشغَّل في CI على كل push)
PYTHONPATH=. pytest -q ../../tests/ -m "not integration and not smoke"

# اختبار تكامل: رفض path traversal على /asr/download
PYTHONPATH=. pytest -q ../../tests/test_api_units.py::test_download_path_traversal_integration -m integration

# اختبارات الأمان
PYTHONPATH=. pytest -q ../../tests/test_auth_security.py ../../tests/test_secure_endpoints.py

# دخان ASR (يتخطى تلقائيًا إن لم يوجد model.bin محليًا)
PYTHONPATH=. pytest -q ../../tests/test_asr_smoke.py -m smoke
```

**CI (`/.github/workflows/ci.yml`):**
- workflow واحد: تثبيت deps مرة واحدة ثم `pytest ../../tests/`
- يشمل: unit + security + integration (path traversal)
- اختبار الدخان ASR يعمل إن وُجدت أوزان محلية، وإلا `skip` بدون فشل
- يعمل على `push`/`PR` لـ `nabra`, `main`, `master`

---

## 11) ملاحظات تشغيل مهمة

- الأفضل توحيد البيئة على (`.venv/`)؛ `run.sh` ينشئها تلقائيًا. مجلد `venv/` القديم مدعوم للتوافق — راجع `scripts/migrate_to_dot_venv.sh`.
- عند مشاكل CUDA/نماذج، افحص أولاً `/health`.
- لتجربة الواجهة مباشرة استخدم `http://127.0.0.1:8000/`.

---

## 12) الترخيص

MIT
