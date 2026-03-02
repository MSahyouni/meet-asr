# scripts/prepare_rag_arabictextlarge.py
import os, glob, json, pathlib
import numpy as np, faiss
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
import pyarrow.parquet as pq

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "rag" / "arabictext_large"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ابحث عن مسار الـ snapshots تلقائيًا (ويندوز)
home = pathlib.Path.home()
base = home / ".cache" / "huggingface" / "hub"
cands = [
    base / "datasets--Jr23xd23--ArabicText-Large" / "snapshots" / "*" / "*.parquet",
    base / "datasets--j23xd23--ArabicText-Large" / "snapshots" / "*" / "*.parquet",
]
parquet_glob = None
for pat in cands:
    fs = glob.glob(str(pat))
    if fs:
        parquet_glob = str(pat); break

# مسار مخصص اختياري عبر متغير بيئة
parquet_glob = os.getenv("ARABICTEXT_PARQUET_GLOB", parquet_glob)

if not parquet_glob:
    raise SystemExit("لم أجد ملفات Parquet. مرّر المسار عبر ARABICTEXT_PARQUET_GLOB، مثل: C:\\Users\\..\\snapshots\\*\\*.parquet")

files = sorted(glob.glob(parquet_glob))
print(f"[+] Parquet files: {len(files)}")

def rows_from_parquet(paths):
    for p in paths:
        table = pq.read_table(p)
        cols = {name: table.column(name) for name in table.schema.names}
        n = table.num_rows
        for i in range(n):
            # حاول حقول شائعة
            text = None
            for key in ("text","content","article","body"):
                if key in cols:
                    v = cols[key][i].as_py()
                    if v: text = str(v); break
            if text and text.strip():
                yield text.strip()

# Prefer local model from data/models if available
_e5_local = ROOT / "data" / "models" / "multilingual-e5-base"
_e5_model = _e5_local.as_posix() if _e5_local.exists() else "intfloat/multilingual-e5-base"
print(f"[+] Loading embedding model from: {_e5_model}")
model = SentenceTransformer(_e5_model)
dims = model.get_sentence_embedding_dimension()
index = faiss.IndexFlatIP(dims)

docs_path = OUT_DIR / "docs.jsonl"
emb_list = []

with open(docs_path, "w", encoding="utf-8") as f:
    buf_txt, buf_emb = [], []
    for text in tqdm(rows_from_parquet(files), desc="Encoding"):
        emb = model.encode(text, normalize_embeddings=True)
        buf_txt.append({"text": text})
        buf_emb.append(emb.astype("float32"))
        if len(buf_emb) >= 1024:
            index.add(np.stack(buf_emb))
            for d in buf_txt:
                json.dump(d, f, ensure_ascii=False); f.write("\n")
            buf_txt, buf_emb = [], []
    if buf_emb:
        index.add(np.stack(buf_emb))
        for d in buf_txt:
            json.dump(d, f, ensure_ascii=False); f.write("\n")

faiss.write_index(index, str(OUT_DIR / "index.faiss"))
print("✅ جاهز:", OUT_DIR)
