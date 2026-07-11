# storage/naming.py — معرّفات وأسماء ملفات مرتبطة بوقت التسجيل
from __future__ import annotations

import re
import secrets
from datetime import datetime


_SAFE_PREFIX_RE = re.compile(r"[^a-z0-9]+")


def new_timestamped_id(prefix: str = "job") -> str:
    """Return a filesystem-safe id embedding local date/time.

    Example: ``asr_20260711_112014_a1b2c3d4``
    """
    safe = _SAFE_PREFIX_RE.sub("_", (prefix or "job").strip().lower()).strip("_") or "job"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = secrets.token_hex(4)
    return f"{safe}_{ts}_{suffix}"
