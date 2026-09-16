"""Configuration centralisée, alimentée par les variables d'environnement."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SOREMED - Plateforme locale"
    environment: str = "development"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./database/soremed.db"
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 480
    cors_origins: str = "http://localhost:5173"
    upload_dir: str = "../uploads"
    backup_dir: str = "./database/backups"
    bootstrap_admin_email: str
    bootstrap_admin_password: str
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
