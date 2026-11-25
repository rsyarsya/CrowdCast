import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)


def test_settings_require_secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(_env_file=None)


def test_settings_require_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    "raw",
    [
        "http://a.test,http://b.test",
        '["http://a.test", "http://b.test"]',
    ],
)
def test_cors_origins_accept_csv_and_json(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    monkeypatch.setenv("BACKEND_CORS_ORIGINS", raw)
    settings = Settings(_env_file=None)
    assert settings.BACKEND_CORS_ORIGINS == ["http://a.test", "http://b.test"]


def test_secret_key_is_hidden_in_repr() -> None:
    settings = Settings(_env_file=None)
    assert settings.SECRET_KEY.get_secret_value() not in repr(settings)


def test_password_hash_roundtrip() -> None:
    hashed = get_password_hash("rahasia123")
    assert hashed != "rahasia123"
    assert verify_password("rahasia123", hashed)
    assert not verify_password("salah", hashed)


def test_access_token_roundtrip() -> None:
    token = create_access_token(subject=7, role="admin")
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "7"
    assert payload["role"] == "admin"


def test_tampered_token_is_rejected() -> None:
    token = create_access_token(subject=7)
    assert decode_access_token(token + "x") is None
