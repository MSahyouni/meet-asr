# prepare_rag_stream.py  —  FAST (pyarrow) + robust column detection
import os, json, argparse, pathlib, re
from typing import List, Optional
import numpy as np
import faiss
import pyarrow.parquet as pq
from tqdm import tqdm
from sentence_transformers import SentenceTransformer

RAG_DIR   = pathlib.Path("data/rag/arabictext_large")
DOCS_PATH = RAG_DIR / "docs.jsonl"
INDEX_PATH= RAG_DIR / "index.faiss"

# أين ملفات parquet محليًا
PARQUET_DIR = pathlib.Path("data/datasets/ArabicText-Large/data")

# نموذج التضمين (محلي إن وجد)
EMB_LOCAL = pathlib.Path("data/models/multilingual-e5-base")
EMB_NAME  = "intfloat/multilingual-e5-base"
EMB = SentenceTransformer(EMB_LOCAL.as_posix() if EMB_LOCAL.exists() else EMB_NAME)

# أعمدة نص محتملة داخل parquet
TEXT_KEYS = ["text","content","article","body","data","text_clean","clean_text","paragraph","raw"]

def list_parquet_files(max_files: Optional[int]=None) -> List[str]:
    if not PARQUET_DIR.exists():
        print(f"[!] لم أجد المجلد: {PARQUET_DIR.as_posix()}")
        return []
    files = sorted(str(p.resolve()) for p in PARQUET_DIR.glob("*.parquet"))
    if max_files is not None:
        files = files[:max_files]
    print(f"[+] Parquet files: {len(files)}")
    for f in files[:3]:
        print(f"    - {pathlib.Path(f).name}")
    return files

def load_or_init_index(dim: int):
    if INDEX_PATH.exists():
        idx = faiss.read_index(INDEX_PATH.as_posix())
        if idx.d != dim:
            raise RuntimeError(f"index dim={idx.d} != emb dim={dim}")
        print(f"[+] Loaded index: {INDEX_PATH} (dim={idx.d}, ntotal={idx.ntotal})")
        return idx
    idx = faiss.IndexFlatIP(dim)  # cosine with normalized vectors
    print(f"[+] New index (dim={dim})")
    return idx

def count_lines(path: pathlib.Path) -> int:
    if not path.exists(): return 0
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return sum(1 for _ in f)

def write_jsonl(path: pathlib.Path, rows: List[dict], append: bool=True):
    mode = "a" if append and path.exists() else "w"
    with open(path, mode, encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

def clean_text(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s

def pick_text_from_row(row: dict) -> Optional[str]:
    # جرّب مفاتيح نص جاهزة
    for k in TEXT_KEYS:
        v = row.get(k)
        if isinstance(v, str) and v.strip():
            return v
    # وإلا: دمّج القيم النصية
    parts = [str(v) for v in row.values() if isinstance(v, str) and v.strip()]
    return (" ".join(parts).strip()) if parts else None

def main(limit: int, append: bool, batch_size: int, checkpoint_every: int, max_files: Optional[int]):
    RAG_DIR.mkdir(parents=True, exist_ok=True)
    files = list_parquet_files(max_files=max_files)
    if not files:
        print("[!] لا توجد ملفات Parquet محلية. ضعها في data/datasets/ArabicText-Large/data/")
        return

    # اطبع سكيمة أول ملف للمراجعة (يساعد لو ما في نص)
    try:
        sch = pq.ParquetFile(files[0]).schema_arrow
        print("[i] أول ملف — الأعمدة:", [f.name for f in sch])
    except Exception as e:
        print("[?] فشل قراءة سكيمة:", e)

    dim = EMB.get_sentence_embedding_dimension()
    index = load_or_init_index(dim)
    before_lines = count_lines(DOCS_PATH) if append else 0
    print(f"[+] docs.jsonl current lines: {before_lines}")

    total_added = 0
    buf_txt, buf_enc = [], []

    pbar = tqdm(total=(limit if limit > 0 else None), unit="rows", desc="Encoding", mininterval=0.3)

    def flush_buffers():
        nonlocal total_added, buf_txt, buf_enc
        if not buf_txt: return
        vecs = EMB.encode(buf_enc, normalize_embeddings=True, batch_size=64, convert_to_numpy=True)
        index.add(vecs.astype("float32"))
        write_jsonl(DOCS_PATH, buf_txt, append=True)
        total_added += len(buf_txt)
        pbar.update(len(buf_txt))
        buf_txt, buf_enc = [], []
        if checkpoint_every and (total_added % checkpoint_every == 0):
            faiss.write_index(index, INDEX_PATH.as_posix())

    for fp in files:
        if limit and total_added >= limit: break
        pf = pq.ParquetFile(fp)
        for rg in range(pf.num_row_groups):
            table = pf.read_row_group(rg)     # كل الأعمدة
            cols = {n: table[n].to_pylist() for n in table.schema.names}
            n = len(next(iter(cols.values()))) if cols else 0
            for i in range(n):
                row = {k: cols[k][i] for k in cols}
                txt = pick_text_from_row(row)
                if not txt: continue
                txt = clean_text(txt)
                if not txt: continue

                buf_txt.append({"text": txt})
                buf_enc.append("passage: " + txt)

                if len(buf_txt) >= batch_size:
                    flush_buffers()
                    if limit and total_added >= limit: break
            if limit and total_added >= limit: break
        if limit and total_added >= limit: break

    flush_buffers()
    faiss.write_index(index, INDEX_PATH.as_posix())
    pbar.close()
    print(f"✅ تم: أُضيف {total_added} مقطعاً.")
    print(f"📄 {DOCS_PATH.as_posix()}")
    print(f"🧠 {INDEX_PATH.as_posix()} (ntotal={index.ntotal})")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=5000)
    ap.add_argument("--append", action="store_true")
    ap.add_argument("--batch-size", type=int, default=256)
    ap.add_argument("--checkpoint-every", type=int, default=1000)
    ap.add_argument("--max-files", type=int, default=None, help="اقرأ فقط أول N ملف Parquet")
    args = ap.parse_args()
    main(args.limit, args.append, args.batch_size, args.checkpoint_every, args.max_files)
