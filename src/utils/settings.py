"""Application settings loaded from environment / .env file.

Validators ensure obvious placeholder secrets are rejected at startup
so deployments fail fast when secrets are not configured.
"""
from pydantic_settings import BaseSettings
from pydantic import model_validator
import os
import warnings


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    admin_email: str
    admin_password: str
    storage_secret: str = ""
    attachments_root: str = "/data/attachments"
    jwt_expire_hours: int = 24
    log_level: str = "INFO"
    api_base_url: str = "http://127.0.0.1:8080"
    cookie_secure: bool = True  # set COOKIE_SECURE=false for local dev over HTTP

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @model_validator(mode="after")
    def _validate_secrets(self):
        # SECRET_KEY: reject obvious placeholders and short keys
        is_dev = os.getenv("DEV_MODE", "false").lower() in ("1", "true", "yes")

        key = (self.secret_key or "").strip()
        if (
            len(key) < 32
            or "replace_with" in key.lower()
            or "dev_secret" in key.lower()
        ):
            msg = (
                "SECRET_KEY must be at least 32 characters and not a placeholder. "
                "Generate one with: openssl rand -hex 32"
            )
            if is_dev:
                warnings.warn(msg)
            else:
                raise ValueError(msg)

        # ADMIN_PASSWORD: ensure not left as the default placeholder
        pwd = (self.admin_password or "").strip()
        if pwd in ("changeme_on_first_boot", "changeme"):
            msg = (
                "ADMIN_PASSWORD must be changed from the default. "
                "Set a strong password in .env before first boot."
            )
            if is_dev:
                warnings.warn(msg)
            else:
                raise ValueError(msg)

        # STORAGE_SECRET: derive from SECRET_KEY if not explicitly provided
        if not (self.storage_secret or "").strip():
            # derive a distinct value so it's never identical to SECRET_KEY
            self.storage_secret = key + "_nicegui_storage"

        return self


settings = Settings()  # type: ignore[call-arg]
