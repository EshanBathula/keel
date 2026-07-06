"""Application configuration.

All settings can be overridden with environment variables (see .env.example).
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Keel API"
    database_url: str = "sqlite:///./keel.db"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours
    cors_origins: str = "http://localhost:5173,http://localhost:4173"

    class Config:
        env_file = ".env"


settings = Settings()
