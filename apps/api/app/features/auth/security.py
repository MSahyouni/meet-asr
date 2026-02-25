import base64
import hashlib
import hmac
import json
import os
import time
from typing import Dict, Optional


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode((data + pad).encode("ascii"))


def _jwt_secret() -> str:
    return os.getenv("JWT_SECRET", "meet-asr-offline-secret-change-me")


def token_ttl_seconds() -> int:
    try:
        return max(300, int(os.getenv("JWT_EXPIRES_SECONDS", "86400")))
    except Exception:
        return 86400


def create_access_token(email: str, user_id: str, full_name: str) -> str:
    now = int(time.time())
    payload = {
        "sub": email,
        "uid": user_id,
        "name": full_name,
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
        exp = int(payload.get("exp", 0))
        if exp <= int(time.time()):
            return None
        return payload
    except Exception:
        return None


def extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    value = authorization.strip()
    if not value.lower().startswith("bearer "):
        return None
    token = value[7:].strip()
    return token or None


def resolve_email_from_authorization(authorization: Optional[str]) -> Optional[str]:
    token = extract_bearer_token(authorization)
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    email = payload.get("sub")
    return str(email) if email else None


def resolve_payload_from_authorization(authorization: Optional[str]) -> Optional[Dict[str, str]]:
    token = extract_bearer_token(authorization)
    if not token:
        return None
    return decode_access_token(token)


def is_admin_email(email: Optional[str]) -> bool:
    if not email:
        return False
    raw = os.getenv("ADMIN_EMAILS", "").strip()
    if not raw:
        return False
    admin_emails = {item.strip().lower() for item in raw.split(",") if item.strip()}
    return email.lower() in admin_emails
