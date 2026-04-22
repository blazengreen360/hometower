import os
import warnings

from pydantic import model_validator
from pydantic_settings import BaseSettings


_DEV_MODE_VALUES = ("1", "true", "yes")
_DEFAULT_ADMIN_PASSWORDS = ("changeme_on_first_boot", "changeme")
_SECRET_KEY_ERROR = (
    "SECRET_KEY must be at least 32 characters and not a placeholder. "
    "Generate one with: openssl rand -hex 32"
)
_ADMIN_PASSWORD_ERROR = (
    "ADMIN_PASSWORD must be changed from the default. "
    "Set a strong password in .env before first boot."
)


"""Application settings loaded from environment / .env file.

Validators ensure obvious placeholder secrets are rejected at startup
so deployments fail fast when secrets are not configured.
"""


def _is_dev_mode() -> bool:
    return os.getenv("DEV_MODE", "false").lower() in _DEV_MODE_VALUES


def _is_invalid_secret_key(secret_key: str) -> bool:
    lowered_key = secret_key.lower()
    return (
        len(secret_key) < 32
        or "replace_with" in lowered_key
        or "dev_secret" in lowered_key
    )


def _warn_or_raise(message: str, is_dev: bool) -> None:
    if is_dev:
        warnings.warn(message)
        return
    raise ValueError(message)


def _derive_storage_secret(secret_key: str, storage_secret: str) -> str:
    if storage_secret.strip():
        return storage_secret
    return secret_key + "_nicegui_storage"


def _validate_secret_key(secret_key: str, is_dev: bool) -> None:
    if _is_invalid_secret_key(secret_key):
        _warn_or_raise(_SECRET_KEY_ERROR, is_dev)


def _validate_admin_password(admin_password: str, is_dev: bool) -> None:
    if admin_password in _DEFAULT_ADMIN_PASSWORDS:
        _warn_or_raise(_ADMIN_PASSWORD_ERROR, is_dev)


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    admin_email: str
    admin_password: str
    attachments_root: str = "/data/attachments"
    storage_secret: str = ""
    jwt_expire_hours: int = 24
    log_level: str = "INFO"
    api_base_url: str = "http://127.0.0.1:8080"
    cookie_secure: bool = True  # set COOKIE_SECURE=false for local dev over HTTP

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @model_validator(mode="after")
    def _validate_secrets(self):
        key = (self.secret_key or "").strip()
        is_dev = _is_dev_mode()
        pwd = (self.admin_password or "").strip()
        _validate_secret_key(key, is_dev)
        _validate_admin_password(pwd, is_dev)
        self.storage_secret = _derive_storage_secret(key, self.storage_secret or "")

        return self


settings = Settings()  # type: ignore[call-arg]
