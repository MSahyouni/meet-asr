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

🖥️ واجهة ويب (Gradio)

⚡ دعم التشغيل على CPU أو GPU

🐳 دعم Docker و Docker Compose

📦 نشر تلقائي على GitHub Container Registry



---

🧠 كيف يعمل

يعتمد Meet-ASR على فصل واضح بين الواجهة والمعالجة:

API

Enhance → ASR → Diarization → Summarize


Web UI

واجهة استخدام تتواصل مع الـ API فقط


يمكن لأي تطبيق خارجي استخدام الـ API مباشرة


> تم حذف ملف app.py والاعتماد على API + Web Proxy فقط.




---

🗂️ بنية المشروع

api.py
asr_core.py
nlp_core.py
app_api_proxy.py
requirements.txt
requirements.web.txt

docker/
├─ Dockerfile.api
├─ Dockerfile.web
├─ docker-compose.yml
└─ docker-compose.prod.yml

.github/workflows/
├─ docker-test.yml
└─ docker-publish.yml


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
..venv\Scripts\activate    (Windows)

pip install -U pip
pip install -r requirements.txt

لتشغيل الواجهة: pip install -r requirements.web.txt


---

3) إعداد متغيرات البيئة (اختياري)

أنشئ ملف .env:

HF_TOKEN=hf_xxxxxxxxxxxxxxxxx
WHISPER_MODEL=large-v3

MODELS_DIR=./models
OUTPUTS_DIR=./data/outputs
SPK_DIR=./voices


---

▶️ تشغيل API

uvicorn api:app --host 0.0.0.0 --port 8000

تحقق من الصحة: http://127.0.0.1:8000/health


---

🖥️ تشغيل الواجهة (Web UI)

في Terminal آخر (بعد تشغيل API):

python app_api_proxy.py

ثم افتح: http://127.0.0.1:7860


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

POST /transcribe
POST /transcribe-batch
POST /summarize
GET /health


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
ghcr.io/<username>/meetasr-web:latest


---

📄 الترخيص

MIT License
