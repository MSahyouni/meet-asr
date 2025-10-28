FROM python:3.10-slim

RUN apt-get update && apt-get install -y ffmpeg libsndfile1 git && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

# مسارات ثابتة للتخزين المحلي
ENV ASR_DATA_DIR=/app/data \
    HF_HOME=/app/data/.hf \
    TRANSFORMERS_VERBOSITY=error
RUN mkdir -p /app/data/outputs /app/data/models /app/data/voices /app/data/.hf

RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

EXPOSE 8000
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
