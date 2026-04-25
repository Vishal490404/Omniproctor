from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Omniproctor API"
    api_v1_prefix: str = "/api/v1"
    debug: bool = True

    database_url: str = "postgresql+psycopg://omniproctor:omniproctor@db:5432/omniproctor"

    secret_key: str = "change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    cors_origins: list[str] = ["*"]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
