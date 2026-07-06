"""Unit tests for the production JWT-secret guard."""
import pytest

from app.config import Settings, _check_production_secret


def test_production_with_default_secret_raises():
    s = Settings(env="production", jwt_secret="change-me-in-production")
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        _check_production_secret(s)


def test_production_with_custom_secret_is_fine():
    s = Settings(env="production", jwt_secret="a-real-random-secret-value")
    _check_production_secret(s)  # must not raise


def test_development_with_default_secret_is_fine():
    s = Settings(env="development", jwt_secret="change-me-in-production")
    _check_production_secret(s)  # must not raise
