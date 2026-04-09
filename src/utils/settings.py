"""Application settings loaded from environment / .env file."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    admin_email: str
    admin_password: str
    jwt_expire_hours: int = 24
    log_level: str = "INFO"
    api_base_url: str = "http://127.0.0.1:8080"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()  # type: ignore[call-arg]
