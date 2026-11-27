from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher

from app.core.config import get_settings

password_hash = PasswordHash((BcryptHasher(),))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return password_hash.hash(password)


@lru_cache
def _dummy_hash() -> str:
    return password_hash.hash("crowdcast-dummy-password")


def verify_password_or_dummy(plain_password: str, hashed_password: str | None) -> bool:
    """Verify a password, spending the same time when the user does not exist.

    Without the dummy check, a login for an unknown email returns faster than a
    wrong password, which reveals which emails are registered.
    """
    if hashed_password is None:
        password_hash.verify(plain_password, _dummy_hash())
        return False
    return password_hash.verify(plain_password, hashed_password)


def mask_source(source: str) -> str:
    """Hide the password in a URL such as rtsp://user:pass@host/stream.

    Plain file paths and URLs without credentials are returned unchanged.
    """
    parts = urlsplit(source)
    if not parts.scheme or parts.password is None:
        return source
    host = parts.hostname or ""
    if parts.port is not None:
        host = f"{host}:{parts.port}"
    netloc = f"{parts.username}:***@{host}" if parts.username else f"***@{host}"
    return urlunsplit(parts._replace(netloc=netloc))


def create_access_token(
    subject: str | Any,
    role: str = "operator",
    expires_delta: timedelta | None = None,
) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {"sub": str(subject), "role": role, "exp": expire, "iat": now}
    return jwt.encode(
        payload,
        settings.SECRET_KEY.get_secret_value(),
        algorithm=settings.ALGORITHM,
    )


def decode_access_token(token: str) -> dict[str, Any] | None:
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY.get_secret_value(),
            algorithms=[settings.ALGORITHM],
        )
    except jwt.PyJWTError:
        return None


TICKET_TYPE = "ticket"


def create_ticket(subject: str | Any, scope: str) -> str:
    """Short-lived token for URLs the browser opens without headers (<img>, EventSource).

    It only works for `scope` and is never accepted as a Bearer token.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject),
        "typ": TICKET_TYPE,
        "scope": scope,
        "exp": now + timedelta(seconds=settings.STREAM_TICKET_SECONDS),
        "iat": now,
    }
    return jwt.encode(
        payload, settings.SECRET_KEY.get_secret_value(), algorithm=settings.ALGORITHM
    )


def decode_ticket(token: str, scope: str) -> str | None:
    """The ticket's subject, or None when it is invalid, expired, or for another scope."""
    payload = decode_access_token(token)
    if payload is None or payload.get("typ") != TICKET_TYPE or payload.get("scope") != scope:
        return None
    subject = payload.get("sub")
    return str(subject) if subject is not None else None
