from __future__ import annotations

import hashlib
import hmac
import os
from base64 import b64encode
from typing import Any

try:
    from passlib.context import CryptContext  # type: ignore
except Exception:  # noqa: BLE001
    CryptContext = None


PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto") if CryptContext else None


def get_admin_user() -> str:
    return (os.getenv("APP_ADMIN_USER") or "").strip()


def get_password_hash() -> str:
    return (os.getenv("APP_ADMIN_PASSWORD_HASH") or "").strip()


def get_password_plain_fallback() -> str:
    return os.getenv("APP_ADMIN_PASSWORD") or ""


def is_auth_enabled() -> bool:
    return bool(get_admin_user() and (get_password_hash() or get_password_plain_fallback()))


def _verify_with_pbkdf2(password: str, encoded_hash: str) -> bool:
    # format: pbkdf2_sha256$<iterations>$<salt>$<digest_b64>
    try:
        _, rounds_text, salt, digest_b64 = encoded_hash.split("$", 3)
        rounds = int(rounds_text)
        computed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), rounds)
        return hmac.compare_digest(b64encode(computed).decode("utf-8"), digest_b64)
    except Exception:  # noqa: BLE001
        return False


def verify_password(password: str, configured_hash: str, plain_fallback: str = "") -> bool:
    if configured_hash:
        if configured_hash.startswith("$2") and PWD_CONTEXT:
            return bool(PWD_CONTEXT.verify(password, configured_hash))
        if configured_hash.startswith("pbkdf2_sha256$"):
            return _verify_with_pbkdf2(password, configured_hash)
        if configured_hash.startswith("sha256$"):
            return hmac.compare_digest(hashlib.sha256(password.encode("utf-8")).hexdigest(), configured_hash.split("$", 1)[1])
        if PWD_CONTEXT:
            try:
                return bool(PWD_CONTEXT.verify(password, configured_hash))
            except Exception:  # noqa: BLE001
                return False
        return False

    if plain_fallback:
        return hmac.compare_digest(password, plain_fallback)
    return False


def verify_credentials(username: str, password: str) -> bool:
    if not is_auth_enabled():
        return True
    expected_user = get_admin_user()
    if not hmac.compare_digest(username.strip(), expected_user):
        return False
    return verify_password(password, get_password_hash(), get_password_plain_fallback())


def session_is_authenticated(session_data: dict[str, Any] | None) -> bool:
    if not is_auth_enabled():
        return True
    if not isinstance(session_data, dict):
        return False
    return hmac.compare_digest(str(session_data.get("auth_user") or ""), get_admin_user())
