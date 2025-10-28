# tools/index_arabictext.py
# فهرسة ArabicText-Large لـ RAG (تجزئة + تضمين E5 + FAISS) مع دعم GPU/الاستئناف/حفظ مرحلي

import os, json, pathlib, io
from typing import Iterator, Dict, Any, List, Optional, Tuple
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

# ===== إعدادات المسارات =====
DATA_DIR  = pathlib.Path(os.getenv("ASR_DATA_DIR", "data")).resolve()
RAG_DIR   = (DATA_DIR / "rag" / "arabictext_large"); RAG_DIR.mkdir(parents=True, exist_ok=True)
RAW_PATH  = RAG_DIR / "raw.jsonl"          # الناتج من download_arabictext.py
INDEX_PATH= RAG_DIR / "index.faiss"
DOCS_PATH = RAG_DIR / "docs.jsonl"

# ===== إعدادات النماذج/الأحجام =====
EMB_MODEL     = os.getenv("RAG_EMB_MODEL", "intfloat/multilingual-e5-small")  # بديل أسرع: paraphrase-multilingual-MiniLM-L12-v2
CHUNK_SIZE    = int(os.getenv("RAG_CHUNK_SIZE", "1000"))  # عدد أحرف كل مقطع
CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "150"))
BATCH_SIZE    = int(os.getenv("RAG_BATCH", "64"))         # خفّضه على CPU (32 مثلاً)
CHECK_EVERY   = int(os.getenv("RAG_CHECK_EVERY", "5000")) # احفظ مرحليًا كل X مقطع
USE_GPU       = os.getenv("RAG_USE_GPU", "auto")          # auto|1|0

# ===== أدوات =====
def pick_device() -> str:
    if USE_GPU == "1":
        return "cuda"
    if USE_GPU == "0":
        return "cpu"
    # auto
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"

def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> Iterator[str]:
    text = (text or "").strip()
    n, i = len(text), 0
    while i < n:
        j = min(n, i + size)
        yield text[i:j]
        i = j - overlap

def iter_raw_objs(path: pathlib.Path) -> Iterator[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"missing {path}")
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    yield obj
            except Exception:
                continue

def encode_passages(model: SentenceTransformer, passages: List[str]) -> np.ndarray:
    # E5: "passage: " للوثائق
    return model.encode(
        [f"passage: {p}" for p in passages],
        batch_size=BATCH_SIZE,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=True
    ).astype("float32")

def load_existing_docs(path: pathlib.Path) -> Tuple[int, Optional[List[Dict[str, Any]]]]:
    """يعيد (count, None) إن لم يوجد الملف؛ أو (count, None) لتجنّب تحميل كل شيء في الذاكرة."""
    if not path.exists():
        return 0, None
    # عدّ سريع بدون تحميل كامل الذاكرة
    count = 0
    with open(path, "r", encoding="utf-8") as f:
        for _ in f: count += 1
    return count, None

def append_docs(path: pathlib.Path, docs: List[Dict[str, Any]]) -> None:
    with open(path, "a", encoding="utf-8") as f:
        for d in docs:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

def build_or_load_index(dim: int, index_path: pathlib.Path) -> faiss.Index:
    if index_path.exists():
        idx = faiss.read_index(index_path.as_posix())
        if idx.d != dim:
            raise RuntimeError(f"Index dim mismatch: on-disk={idx.d} vs new={dim}")
        return idx
    return faiss.IndexFlatIP(dim)

def main():
    device = pick_device()
    print(f"[RAG] device={device} | model={EMB_MODEL}")
    model = SentenceTransformer(EMB_MODEL, device=device)

    # الاستئناف: ابدأ IDs بعد الموجود
    existing_count, _ = load_existing_docs(DOCS_PATH)
    next_id = existing_count
    print(f"[RAG] resume: existing docs lines = {existing_count}")

    vec_blocks: List[np.ndarray] = []
    pending_docs: List[Dict[str, Any]] = []
    cur_batch_texts: List[str] = []
    cur_batch_meta:  List[Dict[str, Any]] = []

    processed_articles = 0
    total_chunks_written = existing_count

    # إذا كنا نستأنف، فلا توجد طريقة لمعرفة رقم المقال من raw.jsonl سابقًا — لا مشكلة.
    for obj in iter_raw_objs(RAW_PATH):
        processed_articles += 1
        body = (obj.get("text") or obj.get("content") or obj.get("article") or "").strip()
        if not body:
            continue
        title = obj.get("title")
        url   = obj.get("url")
        for c in chunk_text(body):
            meta = {"id": next_id, "text": c}
            if title: meta["title"] = title
            if url:   meta["url"]   = url
            cur_batch_meta.append(meta)
            cur_batch_texts.append(c)
            next_id += 1

            # وصلنا حجم دفعة التضمين
            if len(cur_batch_texts) >= BATCH_SIZE:
                vec = encode_passages(model, cur_batch_texts)
                vec_blocks.append(vec)
                pending_docs.extend(cur_batch_meta)
                cur_batch_texts, cur_batch_meta = [], []

            # حفظ مرحلي
            if (next_id - total_chunks_written) >= CHECK_EVERY:
                if cur_batch_texts:
                    vec = encode_passages(model, cur_batch_texts)
                    vec_blocks.append(vec)
                    pending_docs.extend(cur_batch_meta)
                    cur_batch_texts, cur_batch_meta = [], []

                Xp = np.vstack(vec_blocks).astype("float32")
                dim = Xp.shape[1]
                index = build_or_load_index(dim, INDEX_PATH)
                index.add(Xp)
                faiss.write_index(index, INDEX_PATH.as_posix())
                append_docs(DOCS_PATH, pending_docs)

                total_chunks_written += Xp.shape[0]
                print(f"[RAG] checkpoint: total_vectors={total_chunks_written} articles_seen={processed_articles}")
                vec_blocks.clear()
                pending_docs.clear()

        if (processed_articles % 500) == 0:
            print(f"[RAG] processed articles: {processed_articles}")

    # دفعة أخيرة
    if cur_batch_texts:
        vec = encode_passages(model, cur_batch_texts)
        vec_blocks.append(vec)
        pending_docs.extend(cur_batch_meta)

    if vec_blocks:
        X = np.vstack(vec_blocks).astype("float32")
        dim = X.shape[1]
        index = build_or_load_index(dim, INDEX_PATH)
        index.add(X)
        faiss.write_index(index, INDEX_PATH.as_posix())
        append_docs(DOCS_PATH, pending_docs)
        total_chunks_written += X.shape[0]

    if total_chunks_written == existing_count:
        raise RuntimeError("No new documents collected — RAW_PATH may be empty or already fully indexed.")

    print("==== DONE ====")
    print(" index :", INDEX_PATH)
    print(" docs  :", DOCS_PATH)
    print(" vectors indexed:", total_chunks_written)

if __name__ == "__main__":
    main()
