# nlp/models_loader.py — تحميل نماذج من HuggingFace أو مسار محلي
import pathlib
import re
import os

from huggingface_hub import snapshot_download

from ..config import settings
from ..infrastructure.download_retry import run_with_download_retry

_HF_REPO_RE = re.compile(r"^[^/\\]+/[^/\\]+$")


def _is_hf_repo_id(value: str) -> bool:
    s = (value or "").strip()
    if not s or s.startswith(("data/", ".", "/")) or "\\" in s:
        return False
    return bool(_HF_REPO_RE.match(s))


def _looks_like_complete_model_dir(path: pathlib.Path) -> bool:
    """Avoid treating a failed/partial HF download (README + .cache only) as ready."""
    if not path.exists() or not path.is_dir():
        return False
    if not (path / "config.json").exists():
        return False

    index = path / "model.safetensors.index.json"
    bin_index = path / "pytorch_model.bin.index.json"
    if index.exists() or bin_index.exists():
        try:
            import json

            idx_path = index if index.exists() else bin_index
            weight_map = json.loads(idx_path.read_text(encoding="utf-8")).get("weight_map") or {}
            shard_names = sorted(set(weight_map.values()))
            if not shard_names:
                return False
            return all((path / name).exists() and (path / name).stat().st_size > 0 for name in shard_names)
        except Exception:
            return False

    if (path / "model.safetensors").exists() or (path / "pytorch_model.bin").exists():
        return True
    if any(path.glob("*.gguf")):
        return True
    return False


def _resolve_local_path(repo_or_path: str) -> pathlib.Path | None:
    raw = (repo_or_path or "").strip()
    if not raw or _is_hf_repo_id(raw):
        return None
    candidate = pathlib.Path(raw)
    if not candidate.is_absolute():
        candidate = (settings.BASE_DIR / raw).resolve()
    if candidate.is_file() and candidate.exists():
        return candidate
    if candidate.is_dir() and _looks_like_complete_model_dir(candidate):
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
    if local is not None and (local.is_file() or _looks_like_complete_model_dir(local)):
        return local.as_posix()

    target = (settings.MODELS_DIR / subdir).resolve()
    if _looks_like_complete_model_dir(target):
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
        workers = max(1, int(os.getenv("DOWNLOAD_MAX_WORKERS", "4") or "4"))
        return snapshot_download(
            repo_id=repo_id,
            local_dir=target.as_posix(),
            local_dir_use_symlinks=False,
            cache_dir=settings.HF_DIR.as_posix(),
            token=settings.HF_TOKEN,
            max_workers=workers,
        )

    run_with_download_retry(
        _download_once,
        f"nlp:{repo_id}",
        max_attempts=max_download_attempts,
    )
    if not _looks_like_complete_model_dir(target):
        raise FileNotFoundError(
            f"Download finished but model files incomplete under {target} (missing config/weights)."
        )
    return target.as_posix()
