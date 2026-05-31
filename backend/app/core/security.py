from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from cryptography.fernet import Fernet
from jose import JWTError, jwt

from app.core.config import get_settings


ALGORITHM = "HS256"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(subject: str | UUID, *, minutes: int | None = None, token_type: str = "access") -> str:
    settings = get_settings()
    expire = utcnow() + timedelta(minutes=minutes or settings.access_token_expire_minutes)
    payload = {"sub": str(subject), "exp": expire, "type": token_type}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str, *, expected_type: str = "access") -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise ValueError("Invalid token") from exc
    if payload.get("type") != expected_type:
        raise ValueError("Invalid token type")
    return payload


def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_secret(value: str, *, salt: str | None = None) -> str:
    salt_bytes = base64.urlsafe_b64decode(salt.encode()) if salt else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", value.encode("utf-8"), salt_bytes, 160_000)
    salt_b64 = base64.urlsafe_b64encode(salt_bytes).decode()
    digest_b64 = base64.urlsafe_b64encode(digest).decode()
    return f"pbkdf2_sha256${salt_b64}${digest_b64}"


def verify_secret(value: str, encoded: str) -> bool:
    try:
        algorithm, salt, digest = encoded.split("$", 2)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    expected = hash_secret(value, salt=salt).split("$", 2)[2]
    return hmac.compare_digest(expected, digest)


def _fernet() -> Fernet:
    settings = get_settings()
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.secret_key.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str) -> str:
    return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")
