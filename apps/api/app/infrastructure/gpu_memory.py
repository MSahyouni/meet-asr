# infrastructure/gpu_memory.py — تحرير ذاكرة CUDA بين مراحل ASR / NLP / TTS
from __future__ import annotations

import gc
import logging
from typing import Optional

_log = logging.getLogger("gpu_memory")


def cuda_empty_cache(reason: str = "") -> None:
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            if reason:
                _log.info("CUDA cache cleared (%s)", reason)
    except Exception as e:
        _log.debug("cuda_empty_cache skipped: %s", e)


def cuda_mem_allocated_mb() -> Optional[float]:
    try:
        import torch

        if not torch.cuda.is_available():
            return None
        return float(torch.cuda.memory_allocated() / (1024 * 1024))
    except Exception:
        return None
