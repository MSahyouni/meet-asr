# nlp/models_loader.py — تحميل نماذج من HuggingFace أو مسار محلي
import pathlib

from huggingface_hub import snapshot_download

from ..config import settings
from ..infrastructure.download_retry import run_with_download_retry


def ensure_local(repo_or_path: str, subdir: str, allow_download: bool = True) -> str:
    p = pathlib.Path(repo_or_path)
    if p.exists():
        return p.as_posix()
    target = (settings.MODELS_DIR / subdir).resolve()
    if target.exists() and any(target.rglob("*")):
        return target.as_posix()
    if not allow_download:
        raise FileNotFoundError(
            f"Model not found locally at {target}. Downloads are disabled (allow_download=False)."
        )

    target.mkdir(parents=True, exist_ok=True)
    def _download_once():
        return snapshot_download(
            repo_id=repo_or_path,
            local_dir=target.as_posix(),
            local_dir_use_symlinks=False,
            cache_dir=settings.HF_DIR.as_posix(),
            token=settings.HF_TOKEN,
        )

    run_with_download_retry(_download_once, f"nlp:{repo_or_path}")
    return target.as_posix()
