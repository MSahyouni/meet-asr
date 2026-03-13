# Meet-ASR (نَبْرَة)

منصة محلية (Offline-first) للاستماع والتحويل والتلخيص وتوليد الصوت، مبنية على FastAPI مع واجهة ويب مدمجة.

- ASR: تفريغ صوتي + تمييز متحدثين.
- NLP: تلخيص + كلمات مفتاحية + NER.
- TTS: MMS عربي + XTTS v2 + Habibi (لهجات عربية متعددة).
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
- توجد مسارات حديثة مهيكلة (`/asr/*`, `/nlp/*`, `/tts/*`) 
- ويوجد أيضًا توافق خلفي عبر طبقة `app/compat` (مثل `/transcribe`, `/summarize`, `/tts`).

---

## 2) بنية المشروع

```text
meet-asr/
├─ apps/
│  ├─ api/                    # FastAPI backend
│  │  ├─ api.py
│  │  ├─ requirements.txt
│  │  └─ app/
│  │     ├─ main.py
│  │     ├─ config.py
│  │     ├─ routers/
│  │     ├─ compat/
│  │     └─ features/
├─ nabra/                     # Flutter app (اختياري)
├─ static/frontend/            # واجهة HTML/CSS/JS المدمجة
├─ data/
│  ├─ models/                  # نماذج محلية
│  ├─ outputs/                 # مخرجات ASR/TTS/NLP
│  ├─ voices/                  # بصمات XTTS v2 لكل مستخدم
│  └─ meetasr.sqlite3          # قاعدة SQLite المحلية
├─ docker/Dockerfile.api
├─ docker-compose.yml
├─ docker-compose.prod.yml
├─ run.ps1
├─ run.bat
└─ scripts/docker.ps1
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

> السكربت لا يثبّت المتطلبات تلقائيًا.

### التشغيل اليدوي
```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -U pip
pip install -r apps/api/requirements.txt

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

أهم المتغيرات:
- `ASR_ENV`, `ASR_ALLOWED_ORIGINS`
- `JWT_SECRET`, `JWT_EXPIRES_SECONDS`, `JWT_ISSUER`, `JWT_AUDIENCE`, `ADMIN_EMAILS`
- `WHISPER_MODEL`, `WHISPER_DEVICE`, `WHISPER_COMPUTE`
- `TTS_MMS_ENABLED`, `TTS_PREPROCESS_ENABLED`
- `RAG_ENABLE`, `RAG_EMB_MODEL`

ملاحظات:
- التطبيق يحمّل `.env` من `apps/api/.env` محليًا.
- في Docker، ملف `docker-compose*.yml` يمرر `.env` من جذر المشروع إلى الحاوية.
- عند تغيير إعدادات جوهرية، حدّث القالبين معًا (`apps/api/.env.example` و`.env.example`).

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
- وضع `engine=auto` يعطي أولوية لـ XTTS v2 عند وجود بصمة للمستخدم، ثم fallback تلقائي إلى TTS العربي.
- **تجريبي/اختياري:** `engine=habibi` (Unified/Specialized لهجات عربية متعددة) ويتطلب:
  - تثبيت اختياري: `pip install habibi-tts`
  - `user_email` + عينة صوت مرفوعة مسبقًا
  - `ref_text` (نص مطابق لعينة الصوت المرجعية) — يمكن حفظه مرة واحدة عند رفع العينة عبر `POST /tts/voice-sample`
  - `dialect` اختياري (`UNK|MSA|SAU|UAE|ALG|IRQ|EGY|MAR|OMN|TUN|LEV|SDN|LBY`)
- XTTS v2 بصمات لكل مستخدم:
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
```powershell
pytest -q ../../tests/test_auth_security.py ../../tests/test_secure_endpoints.py
```

اختبار أوسع:
```powershell
pytest -q ../../tests/test_api_units.py
```

---

## 11) ملاحظات تشغيل مهمة

- الأفضل توحيد البيئة على (`.venv`)؛ السكربت يدعم (`venv`) القديم للتوافق.
- عند مشاكل CUDA/نماذج، افحص أولاً `/health`.
- لتجربة الواجهة مباشرة استخدم `http://127.0.0.1:8000/`.

---

## 12) الترخيص

MIT
