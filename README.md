# Meet-ASR 🎤

![Python CI](https://github.com/MSahyouni/meet-asr/actions/workflows/python-ci.yml/badge.svg)
![License](https://img.shields.io/github/license/MSahyouni/meet-asr)

تطبيق للتعرف على الكلام (Speech Recognition) يعمل أوفلاين باستخدام **Python + Whisper + Gradio**،
مع دعم **تمييز المتكلمين (Diarization)** + **تلخيص النصوص**.
يتم تطوير نسخة أندرويد باستخدام **Flutter**.
يدعم التكامل عبر **REST API (FastAPI)**، مع ضمان الجودة عبر **GitHub Actions CI/CD**.

---

## 📂 مكونات المشروع

* `app.py` : الواجهة التفاعلية (Gradio UI).
* `asr_core.py` : المنطق الأساسي (ASR + تحسين الصوت + تمييز المتكلمين + تلخيص).
* `api.py` : واجهة REST API (FastAPI).
* `requirements.txt` : المكتبات المطلوبة.
* `models/` : النماذج الصوتية (Whisper + Speaker Recognition).
* `tests/` : اختبارات دخانية (Smoke tests).
* `.github/workflows/python-ci.yml` : فحص البناء وتشغيل الاختبارات.

---

## 🚀 تشغيل Gradio (واجهة المستخدم)

1. ثبّت المكتبات:

   ```bash
   pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu
   ```
2. شغّل التطبيق:

   ```bash
   python app.py
   ```
3. افتح المتصفح على:

   ```
   http://127.0.0.1:7860
   ```

   * رفع ملف صوتي أو تسجيل مباشر 🎙️.
   * النتيجة: نص مفرّغ + أسماء المتكلمين (إن فُعّل) + ملخص وكلمات مفتاحية.

---

## 🌐 تشغيل REST API (FastAPI)

1. ثبّت المكتبات (إذا لم تفعل سابقًا):

   ```bash
   pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu
   ```
2. شغّل السيرفر:

   ```bash
   uvicorn api:app --host 0.0.0.0 --port 8000
   ```
3. جرّب بالمتصفح:

   * `/health` → فحص جاهزية.
   * `/docs` → واجهة Swagger للتجربة المباشرة.
   * `/transcribe` → رفع ملف صوتي والحصول على النص + الملخص.
   * `/transcribe-batch` → رفع عدة ملفات دفعة واحدة.

### مثال Curl

```bash
curl -X POST "http://127.0.0.1:8000/transcribe" \
  -F "file=@example.wav" \
  -F "diarize=true"
```

---

## 📱 نسخة Flutter (قيد التطوير)

* موجودة في الفرع: `feat/flutter-app`.
* المهام: رفع ملفات من الموبايل → إرسال للـ API → عرض النص والملخص → تنزيل النتائج.

---

## 🔄 CI/CD

* إعداد GitHub Actions في `.github/workflows/python-ci.yml`.
* يقوم بـ:

  * تثبيت المتطلبات.
  * استيراد `api.py` للتأكد من صحته.
  * تشغيل اختبارات دخانية (Smoke tests).
* أي PR لا يندمج قبل نجاح الـ CI ✅.

---

## 👥 الفريق

* أحمد المصطفى → Flutter UI.
* محمد تركي السيد علي → Backend API + Diarization.
* محمد المصطفى → DevOps CI/CD.
* محمد أبو نديم → مشرف المشروع.

---

## 📎 ملاحظات

* هذا المشروع يعمل أوفلاين (مع نماذج Whisper و SpeechBrain).
* يمكن استخدام **CUDA** إن وُجدت بطاقة GPU.
* يدعم اللغة العربية بشكل كامل (RTL في الواجهة).
