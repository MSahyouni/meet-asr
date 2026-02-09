import os
import pathlib
from pathlib import Path
from dotenv import load_dotenv

# تحميل ملف البيئة قبل أي استخدام لـ os.getenv
ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

import multiprocessing
import torch


def _prefer_local(path: pathlib.Path, fallback: str) -> str:
    """إذا وُجد المسار المحلي خذه، وإلا استخدم الاسم الافتراضي."""
    return path.as_posix() if path.exists() else fallback

class Settings:
    def __init__(self):
        # --- General Paths & Dirs ---
        self.BASE_DIR = pathlib.Path(__file__).resolve().parent
        self.DATA_DIR = (self.BASE_DIR / os.getenv("ASR_DATA_DIR", "data")).resolve()
        self.OUTPUTS_DIR = (self.DATA_DIR / "outputs").resolve()
        self.MODELS_DIR = (self.DATA_DIR / "models").resolve()
        self.SPK_DIR = (self.DATA_DIR / "voices").resolve()
        self.HF_DIR = (self.DATA_DIR / ".hf").resolve()
        self.DATASET_DIR = self.DATA_DIR / "datasets" / "ArabicText-Large" / "data"
        self.KW_DIR = (self.MODELS_DIR / "keywords").resolve()
        self.KW_DIR.mkdir(parents=True, exist_ok=True)
        self.TFIDF_PATH = (self.KW_DIR / "tfidf_ar.joblib").resolve()
        # --- Create Dirs ---
        for d in [self.DATA_DIR, self.OUTPUTS_DIR, self.MODELS_DIR, self.SPK_DIR, self.HF_DIR]:
            d.mkdir(parents=True, exist_ok=True)

        # --- API Settings ---
        self.API_TOKEN = os.getenv("API_TOKEN", "").strip()
        self.MAX_UPLOAD_MB = float(os.getenv("MAX_UPLOAD_MB", "50"))
        self.BASE_URL = os.getenv("BASE_URL", "").strip()
        self.ASR_ALLOWED_ORIGINS = os.getenv("ASR_ALLOWED_ORIGINS", "")
        self.ASR_WARMUP = os.getenv("ASR_WARMUP", "0").lower() in ("1", "true")

        # --- ASR Core (Whisper) Settings ---
        self._HAS_CUDA = torch.cuda.is_available()
        self.WHISPER_MODEL = os.getenv("WHISPER_MODEL", "heavy" if self._HAS_CUDA else "light")
        # تحسين الصوت: off (افتراضي) | light (normalize + highpass) | full (noise reduce + filters)
        self.ENHANCE_MODE = os.getenv("ENHANCE_MODE", "off").lower().strip()
        if self.ENHANCE_MODE not in ("off", "light", "full"):
            self.ENHANCE_MODE = "off"
        self.WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cuda" if self._HAS_CUDA else "cpu")
        self.WHISPER_COMPUTE = os.getenv("WHISPER_COMPUTE", "float16" if self.WHISPER_DEVICE == "cuda" else "int8_float32")
        self.GPU_ID = int(os.getenv("GPU_ID", "0"))
        self.CPU_THREADS = max(1, os.cpu_count() // 2 if os.cpu_count() else 1)
        self.ASR_LOG_LOAD = os.getenv("ASR_LOG_LOAD", "1").lower() in ("1", "true")

        # --- File Types ---
        self.ALLOWED_EXT = {".wav", ".mp3", ".m4a", ".mp4", ".ogg", ".flac", ".webm", ".aac", ".3gp", ".opus"}
        self.DOWNLOAD_ALLOW = {".txt", ".srt", ".vtt", ".json", ".wav"}

        # --- NLP & Summarization Models ---
        self.HF_TOKEN = os.getenv("HF_TOKEN", "").strip() or None
        
        # mT5 Summarizer (lite mode)
        _sum_mt5_dir = self.MODELS_DIR / "summarizers" / "mT5_XLSum"
        self.SUMMARIZER_MODEL = os.getenv("SUMMARIZER_MODEL", _prefer_local(_sum_mt5_dir, "csebuetnlp/mT5_multilingual_XLSum"))

        # Jais Summarizer (ultra mode)
        self.ULTRA_MODEL = os.getenv("ULTRA_MODEL", "inceptionai/jais-13b-chat")
        self.ULTRA_4BIT = os.getenv("ULTRA_4BIT", "1").lower() in ("1", "true", "yes")
        self.ULTRA_TRUST_REMOTE = os.getenv("ULTRA_TRUST_REMOTE", "1").lower() in ("1", "true")
        self.ULTRA_PROMPT_MODE = os.getenv("ULTRA_PROMPT_MODE", "auto").lower()
        self.HF_DEVICE_ID = int(os.getenv("HF_DEVICE_ID", "-1")) # Transformers pipeline device

        # --- Punctuation & NER ---
        _punct_dir = self.MODELS_DIR / "punctuation" / "arabic_punct"
        self.PUNCT_MODEL = os.getenv("PUNCT_MODEL", _prefer_local(_punct_dir, "Alireza1044/byt5-small-arabic-punctuation"))
        _ner_dir = self.MODELS_DIR / "ner" / "arabic_ner"
        self.NER_MODEL = os.getenv("NER_MODEL", _prefer_local(_ner_dir, "CAMeL-Lab/bert-base-arabic-camelbert-ner"))

        # --- Summarization Limits ---
        self.SUM_MAX_INPUT_TOKENS = max(256, int(os.getenv("SUM_MAX_INPUT_TOKENS", "800")))
        self.SUM_MAX_PARTS = max(1, int(os.getenv("SUM_MAX_PARTS", "8")))

        # --- RAG Settings ---
        self.RAG_ENABLED = os.getenv("RAG_ENABLE", "0").lower() in ("1", "true")
        self.RAG_DIR = self.DATA_DIR / "rag" / "arabictext_large"
        _e5_base_dir = self.MODELS_DIR / "multilingual-e5-base"
        self.RAG_EMB_MODEL = os.getenv("RAG_EMB_MODEL", _prefer_local(_e5_base_dir, "intfloat/multilingual-e5-base"))
        os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", self.MODELS_DIR.as_posix())

        # --- TTS (Kokoro) — optional diacritization before TTS (P2: CAMeL / Farasa) ---
        self.TTS_DIACRITIZE = os.getenv("TTS_DIACRITIZE", "0").lower() in ("1", "true", "yes")

        # --- Output cleanup (P2-3) — delete files under outputs/ older than N hours ---
        self.CLEANUP_MAX_AGE_HOURS = max(1, int(os.getenv("CLEANUP_MAX_AGE_HOURS", "24")))
        self.CLEANUP_INTERVAL_HOURS = max(1, float(os.getenv("CLEANUP_INTERVAL_HOURS", "24")))
        self.CLEANUP_ENABLED = os.getenv("CLEANUP_ENABLED", "1").lower() in ("1", "true", "yes")

        # --- TF-IDF Settings ---
        self.TFIDF_MAX_ROWS = int(os.getenv("TFIDF_MAX_ROWS", "140000"))

        # --- Transcribe queue / concurrency (P2-4) ---
        self.TRANSCRIBE_MAX_QUEUED = max(1, int(os.getenv("TRANSCRIBE_MAX_QUEUED", "20")))
        self.TRANSCRIBE_MAX_CONCURRENT = max(1, int(os.getenv("TRANSCRIBE_MAX_CONCURRENT", "2")))

        # --- Environment Setup ---
        os.environ["HF_HOME"] = str(self.HF_DIR)
        os.environ.pop("TRANSFORMERS_CACHE", None)
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")
        os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")

# Create a single instance of settings to be imported across the project
settings = Settings()