from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./dev.db"
    jwt_secret: str = Field(min_length=32)
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-opus-5-5"


settings = Settings()
