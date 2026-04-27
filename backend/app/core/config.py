from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Dozhim API"
    app_version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    environment: str = "dev"
    database_url: str = "sqlite:///./dozhim.db"
    idempotency_ttl_hours: int = 24
    verification_http_allowed_hosts: str = "127.0.0.1,localhost"
    verification_http_allowed_methods: str = "GET,POST"
    verification_http_max_timeout_seconds: float = 10.0

    model_config = SettingsConfigDict(env_file=".env", env_prefix="DOZHIM_")


settings = Settings()
