# nlp/models_loader.py — تحميل نماذج من HuggingFace أو مسار محلي
import pathlib
import re

from huggingface_hub import snapshot_download

from ..config import settings
from ..infrastructure.download_retry import run_with_download_retry

_HF_REPO_RE = re.compile(r"^[^/\\]+/[^/\\]+$")


def _is_hf_repo_id(value: str) -> bool:
    s = (value or "").strip()
    if not s or s.startswith(("data/", ".", "/")) or "\\" in s:
        return False
    return bool(_HF_REPO_RE.match(s))


def _resolve_local_path(repo_or_path: str) -> pathlib.Path | None:
    raw = (repo_or_path or "").strip()
    if not raw or _is_hf_repo_id(raw):
        return None
    candidate = pathlib.Path(raw)
    if not candidate.is_absolute():
        candidate = (settings.BASE_DIR / raw).resolve()
    if candidate.exists() and (candidate.is_file() or any(candidate.rglob("*"))):
        return candidate
    return None


def ensure_local(
    repo_or_path: str,
    subdir: str,
    allow_download: bool = True,
    hf_repo_id: str | None = None,
    max_download_attempts: int = 5,
) -> str:
    local = _resolve_local_path(repo_or_path)
    if local is not None:
        return local.as_posix()

    target = (settings.MODELS_DIR / subdir).resolve()
    if target.exists() and any(target.rglob("*")):
        return target.as_posix()

    if not allow_download:
        raise FileNotFoundError(
            f"Model not found locally at {target}. Downloads are disabled (allow_download=False)."
        )

    repo_id = repo_or_path if _is_hf_repo_id(repo_or_path) else hf_repo_id
    if not repo_id or not _is_hf_repo_id(repo_id):
        raise FileNotFoundError(
            f"Model not found locally ({repo_or_path}) and no valid HuggingFace repo id was provided."
        )

    target.mkdir(parents=True, exist_ok=True)

    def _download_once():
        return snapshot_download(
            repo_id=repo_id,
            local_dir=target.as_posix(),
            local_dir_use_symlinks=False,
            cache_dir=settings.HF_DIR.as_posix(),
            token=settings.HF_TOKEN,
        )

    run_with_download_retry(
        _download_once,
        f"nlp:{repo_id}",
        max_attempts=max_download_attempts,
    )
    return target.as_posix()
