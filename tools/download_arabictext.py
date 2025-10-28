# tools/download_arabictext.py
import os, pathlib
from huggingface_hub import hf_hub_download, HfApi
from datasets import load_dataset

OUT = pathlib.Path("data/rag/arabictext_large"); OUT.mkdir(parents=True, exist_ok=True)
api = HfApi()
files = [f for f in api.list_repo_files("Jr23xd23/ArabicText-Large", repo_type="dataset")
         if f.lower().endswith((".jsonl",".json",".parquet"))]

if not files:
    raise SystemExit("No data files (jsonl/json/parquet) found in the dataset repo.")

local_files = []
for f in files:
    lf = hf_hub_download(repo_id="Jr23xd23/ArabicText-Large", filename=f, repo_type="dataset")
    local_files.append(lf)
print("Downloaded:", local_files)

# دمج إلى JSONL واحد (لو كانت Json/Jsonl)
jsonls = [p for p in local_files if p.lower().endswith((".jsonl",".json"))]
if jsonls:
    import json
    out_jsonl = OUT/"raw.jsonl"
    with open(out_jsonl, "w", encoding="utf-8") as w:
        for p in jsonls:
            with open(p, "r", encoding="utf-8") as r:
                for line in r:
                    w.write(line if line.strip().startswith("{") else json.dumps({"text": line.strip()}, ensure_ascii=False)+"\n")
    print("Wrote", out_jsonl)
elif any(p.lower().endswith(".parquet") for p in local_files):
    ds = load_dataset("parquet", data_files=[p for p in local_files if p.lower().endswith(".parquet")])["train"]
    out_jsonl = OUT/"raw.jsonl"
    ds.to_json(out_jsonl.as_posix(), orient="records", lines=True, force_ascii=False)
    print("Wrote", out_jsonl)
else:
    raise SystemExit("Unsupported file types.")
