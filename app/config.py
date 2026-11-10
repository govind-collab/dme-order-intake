"""Settings read from environment variables, with .env as a fallback for local runs.

Owns the single `settings` object: the database URL, the JWT secret, the Claude API key and
model, the one browser origin allowed through CORS, and the daily upload limits.
"""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed settings; a missing or short JWT_SECRET stops the app at import.

    The API key is a SecretStr so it never shows up in a repr or a log line.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./dev.db"
    jwt_secret: str = Field(min_length=32)
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-opus-5-5"
    frontend_origin: str | None = None
    daily_upload_limit_per_user: int = Field(default=100, ge=1)
    daily_upload_limit_total: int = Field(default=500, ge=1)


settings = Settings()
