# routers/models.py
from typing import Optional

from fastapi import APIRouter, Header

from app.config import settings
from app.features.auth.deps import require_logged_in_user
from app.server.deps import get_core, check_api_key

router = APIRouter()


@router.get("/models")
def get_available_models(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    auth_error = check_api_key(x_api_key)
    if auth_error:
        return auth_error
    _, login_error = require_logged_in_user(authorization=authorization)
    if login_error:
        return login_error
    try:
        core = get_core()
        return {
            "models": getattr(core, "MODEL_CHOICES", ["light", "heavy"]),
            "default": getattr(core, "DEFAULT_MODEL", settings.WHISPER_MODEL),
        }
    except Exception:
        return {"models": ["light", "heavy"], "default": settings.WHISPER_MODEL}
