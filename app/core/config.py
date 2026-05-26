from pydantic_settings import BaseSettings
from typing import List
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "PythonBackend.dev"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = True
    SECRET_KEY: str = "dev-secret-key-change-in-production-min-32-chars!!"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    DATABASE_URL: str = "sqlite+aiosqlite:///./pythonbackend.db"
    CORS_ORIGINS: List[str] = ["*"]
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_MINUTES: int = 15
    LOG_LEVEL: str = "INFO"
    APP_ENV: str = "development"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",          # ignora variáveis do .env que não estão na classe
    }

    @property
    def is_sqlite(self) -> bool:
        return "sqlite" in self.DATABASE_URL

    @property
    def async_db_url(self) -> str:
        url = self.DATABASE_URL
        if "sqlite:///" in url and "aiosqlite" not in url:
            url = url.replace("sqlite:///", "sqlite+aiosqlite:///")
        if "postgresql://" in url and "asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://")
        return url


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
