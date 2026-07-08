"""Application configuration.

All settings can be overridden with environment variables (see .env.example).
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Keel API"
    env: str = "development"
    database_url: str = "sqlite:///./keel.db"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours
    cors_origins: str = "http://localhost:5173,http://localhost:4173"
    log_level: str = "INFO"

    class Config:
        env_file = ".env"


def _check_production_secret(s: Settings) -> None:
    """Refuse to run in production with the default, publicly-known JWT secret."""
    default_secret = Settings.model_fields["jwt_secret"].default
    if s.env == "production" and s.jwt_secret == default_secret:
        raise RuntimeError(
            "ENV=production but JWT_SECRET is still the default value. Set a long, "
            "random JWT_SECRET (e.g. `openssl rand -hex 32`) before running in production."
        )


settings = Settings()
_check_production_secret(settings)
