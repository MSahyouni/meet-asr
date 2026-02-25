# nlp/models_loader.py — تحميل نماذج من HuggingFace أو مسار محلي
import pathlib

from huggingface_hub import snapshot_download

from ..config import settings


def ensure_local(repo_or_path: str, subdir: str) -> str:
    p = pathlib.Path(repo_or_path)
    if p.exists():
        return p.as_posix()
    target = (settings.MODELS_DIR / subdir).resolve()
    target.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=repo_or_path,
        local_dir=target.as_posix(),
        local_dir_use_symlinks=False,
        cache_dir=settings.HF_DIR.as_posix(),
        token=settings.HF_TOKEN,
    )
    return target.as_posix()
