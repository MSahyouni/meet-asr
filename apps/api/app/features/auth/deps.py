from __future__ import annotations

from typing import Optional, Tuple

from fastapi.responses import JSONResponse

from app.features.auth.security import resolve_email_from_authorization
from app.server.deps import response_error


def require_logged_in_user(
    user_email: Optional[str] = None,
    authorization: Optional[str] = None,
) -> Tuple[Optional[str], Optional[JSONResponse]]:
    """Require a valid JWT session. Optional claimed user_email must match token subject."""
    token_email = resolve_email_from_authorization(authorization)
    if not token_email:
        return None, response_error(401, "login_required", "يجب تسجيل الدخول أولاً")
    claimed = (user_email or "").strip()
    if claimed and claimed.lower() != token_email.lower():
        return None, response_error(
            403,
            "user_email_mismatch",
            "user_email does not match logged-in user",
        )
    return token_email, None
