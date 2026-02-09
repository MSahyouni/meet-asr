# هيكل المشروع — meet-asr

## نقطات الدخول

| الملف | الوظيفة |
|-------|---------|
| **api.py** | خادم FastAPI (تفريغ صوت، تلخيص، NER، تصدير، jobs، متحدثين) |
| **app_api_proxy.py** | واجهة Gradio للاتصال بالـ API |
| **config.py** | إعدادات واحدة للمشروع |

## الحزم والوحدات

### API (الجذر + routers)
- **server/** — حزمة وحدات الخادم:
  - **server/responses.py** — استجابات موحّدة (`response_ok`, `response_error`, `request_id_var`)
  - **server/segments.py** — تحليل وكتابة مقاطع النص (`parse_segments`, `write_segments_json`)
  - **server/jobs.py** — مهام خلفية (transcribe / summary)
  - **server/deps.py** — تبعيات مشتركة للـ routers (`get_core`, `set_limiter`, إعادة تصدير المساعدات)
- **routers/** — مسارات مجزأة: health, transcribe, summarize, nlp, speakers, export, models, jobs

### ASR (تفريغ صوت)
- **asr_core.py** — واجهة توافق خلفي (إعادة تصدير من `asr`)
- **asr/** — صوت، Whisper، ديازة، متحدثين، ترجمات، process

### NLP
- **nlp_core.py** — واجهة توافق خلفي (إعادة تصدير من `nlp`)
- **nlp/** — نص، كلمات مفتاحية، تلخيص، ترقيم، NER، RAG

### واجهة Gradio
- **web/api_client.py** — استدعاءات HTTP للـ API
- **web/ui.py** — واجهة Gradio (Blocks + أحداث)

## سكربتات وملفات أخرى

- **scripts/** — سكربتات مساعدة:
  - **prepare_rag_stream.py** — إعداد RAG (pyarrow + كشف أعمدة)
  - **prepare_rag_arabictextlarge.py** — إعداد RAG من ArabicText-Large
- **tools/** — تحميل وفهرسة ArabicText
- **tests/smoke_test.py** — اختبار استيراد ووجود التطبيق
- **docker/** — Dockerfile و docker-compose

## تبعيات الاستيراد (مبسّطة)

```
api.py → config, server.responses, server.deps, routers/*
routers/* → server.deps, config, (nlp_core, asr_core عبر get_core)
server.deps → server.responses, server.segments, server.jobs, asr_core
asr_core → asr (حزمة)
nlp_core → nlp (حزمة)
app_api_proxy → web.ui
web.ui → web.api_client
```
