# routers/models.py
from fastapi import APIRouter

from config import settings
from server.deps import get_core

router = APIRouter()


@router.get("/models")
def get_available_models():
    try:
        core = get_core()
        return {
            "models": getattr(core, "MODEL_CHOICES", ["light", "heavy"]),
            "default": getattr(core, "DEFAULT_MODEL", settings.WHISPER_MODEL),
        }
    except Exception:
        return {"models": ["light", "heavy"], "default": settings.WHISPER_MODEL}
