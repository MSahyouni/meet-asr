import base64
import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from functools import lru_cache
from typing import Dict, Optional

logger = logging.getLogger(__name__)

WEAK_JWT_DEFAULT = "meet-asr-offline-secret-change-me"
_WEAK_JWT_PLACEHOLDERS = frozenset(
    {
        WEAK_JWT_DEFAULT,
        "change-me",
        "change-me-very-strong-secret",
        "secret",
        "jwt-secret",
        "your-secret-here",
    }
)
MIN_JWT_SECRET_LEN = 32


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode((data + pad).encode("ascii"))


def _jwt_secret() -> str:
    return os.getenv("JWT_SECRET", WEAK_JWT_DEFAULT)


def _is_production_env() -> bool:
    env = (
        os.getenv("ASR_ENV")
        or os.getenv("APP_ENV")
        or os.getenv("ENV")
        or ""
    ).strip().lower()
    return env in {"prod", "production"}


def is_weak_jwt_secret(secret: Optional[str] = None) -> bool:
    value = (secret if secret is not None else _jwt_secret()).strip()
    if not value:
        return True
    if value.lower() in {item.lower() for item in _WEAK_JWT_PLACEHOLDERS}:
        return True
    if len(value) < MIN_JWT_SECRET_LEN:
        return True
    return False


def _jwt_issuer() -> str:
    return (os.getenv("JWT_ISSUER", "meet-asr") or "meet-asr").strip()


def _jwt_audience() -> str:
    return (os.getenv("JWT_AUDIENCE", "meet-asr-api") or "meet-asr-api").strip()


def _validate_jwt_config() -> None:
    """Hard-fail on weak secrets in production (used when minting/decoding tokens)."""
    if _is_production_env() and is_weak_jwt_secret():
        raise RuntimeError(
            "JWT_SECRET must be a strong secret in production "
            f"(not a placeholder, length >= {MIN_JWT_SECRET_LEN})"
        )


def ensure_jwt_secret_at_startup() -> None:
    """
    Startup gate for JWT_SECRET:
    - production: refuse to boot with a weak/default/short secret
    - development: log a clear warning so local setups are not silently unsafe
    """
    if not is_weak_jwt_secret():
        return
    message = (
        "JWT_SECRET is weak or missing (placeholder/default or shorter than "
        f"{MIN_JWT_SECRET_LEN} chars). Set a strong random secret via JWT_SECRET "
        "(e.g. openssl rand -hex 32)."
    )
    if _is_production_env():
        raise RuntimeError(message)
    logger.warning(message)


def token_ttl_seconds() -> int:
    try:
        return max(300, int(os.getenv("JWT_EXPIRES_SECONDS", "86400")))
    except Exception:
        return 86400


def create_access_token(email: str, user_id: str, full_name: str, token_version: int = 0) -> str:
    _validate_jwt_config()
    now = int(time.time())
    payload = {
        "sub": email,
        "uid": user_id,
        "name": full_name,
        "tv": int(token_version),
        "iss": _jwt_issuer(),
        "aud": _jwt_audience(),
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + token_ttl_seconds(),
    }
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    sig = hmac.new(_jwt_secret().encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header_b64}.{payload_b64}.{_b64url_encode(sig)}"


def decode_access_token(token: str) -> Optional[Dict[str, str]]:
    try:
        _validate_jwt_config()
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b64, payload_b64, signature_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        expected_sig = hmac.new(_jwt_secret().encode("utf-8"), signing_input, hashlib.sha256).digest()
        actual_sig = _b64url_decode(signature_b64)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None

        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
        if str(payload.get("iss", "")) != _jwt_issuer():
            return None
        if str(payload.get("aud", "")) != _jwt_audience():
            return None
        exp = int(payload.get("exp", 0))
        if exp <= int(time.time()):
            return None
        return payload
    except Exception:
        return None


def _is_payload_session_valid(payload: Optional[Dict[str, str]]) -> bool:
    if not payload:
        return False
    email = str(payload.get("sub", "") or "")
    if not email:
        return False
    try:
        from app.infrastructure.database import local_db

        user = local_db.get_user(email, include_password=True)
        if not user:
            return False
        token_version = int(payload.get("tv", 0) or 0)
        current_version = int(user.get("token_version", 0) or 0)
        return token_version == current_version
    except Exception:
        return False


def extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    value = authorization.strip()
    if not value.lower().startswith("bearer "):
        return None
    token = value[7:].strip()
    return token or None


def resolve_email_from_authorization(authorization: Optional[str]) -> Optional[str]:
    payload = resolve_payload_from_authorization(authorization)
    if not payload:
        return None
    email = payload.get("sub")
    return str(email) if email else None


def resolve_payload_from_authorization(authorization: Optional[str]) -> Optional[Dict[str, str]]:
    token = extract_bearer_token(authorization)
    if not token:
        return None
    payload = decode_access_token(token)
    if not _is_payload_session_valid(payload):
        return None
    return payload


def is_admin_email(email: Optional[str]) -> bool:
    if not email:
        return False
    raw = os.getenv("ADMIN_EMAILS", "").strip()
    if not raw:
        return False
    admin_emails = _parse_admin_emails(raw)
    return email.lower() in admin_emails


@lru_cache(maxsize=16)
def _parse_admin_emails(raw: str) -> set[str]:
    return {item.strip().lower() for item in raw.split(",") if item.strip()}
