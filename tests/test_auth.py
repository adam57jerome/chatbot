from __future__ import annotations

from app.auth import is_auth_enabled, is_auth_strict_required, session_is_authenticated, verify_credentials


def test_auth_disabled_without_env(monkeypatch):
    monkeypatch.delenv("APP_ADMIN_USER", raising=False)
    monkeypatch.delenv("APP_ADMIN_PASSWORD_HASH", raising=False)
    monkeypatch.delenv("APP_ADMIN_PASSWORD", raising=False)
    assert is_auth_enabled() is False
    assert verify_credentials("x", "y") is True


def test_auth_enabled_with_plain_fallback(monkeypatch):
    monkeypatch.setenv("APP_ADMIN_USER", "admin")
    monkeypatch.delenv("APP_ADMIN_PASSWORD_HASH", raising=False)
    monkeypatch.setenv("APP_ADMIN_PASSWORD", "secret")
    assert is_auth_enabled() is True
    assert verify_credentials("admin", "secret") is True
    assert verify_credentials("admin", "bad") is False


def test_session_is_authenticated(monkeypatch):
    monkeypatch.setenv("APP_ADMIN_USER", "admin")
    monkeypatch.setenv("APP_ADMIN_PASSWORD", "secret")
    assert session_is_authenticated({"auth_user": "admin"}) is True
    assert session_is_authenticated({"auth_user": "other"}) is False


def test_auth_strict_required_blocks_when_not_configured(monkeypatch):
    monkeypatch.setenv("APP_AUTH_REQUIRED", "1")
    monkeypatch.delenv("APP_ADMIN_USER", raising=False)
    monkeypatch.delenv("APP_ADMIN_PASSWORD_HASH", raising=False)
    monkeypatch.delenv("APP_ADMIN_PASSWORD", raising=False)
    assert is_auth_strict_required() is True
    assert verify_credentials("x", "y") is False
    assert session_is_authenticated({"auth_user": "admin"}) is False
