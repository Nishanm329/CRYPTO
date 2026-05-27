"""Configuration management for different environments."""

import os
from typing import Optional
from enum import Enum


class Environment(str, Enum):
    """Application environment."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Config:
    """Base configuration."""

    # Environment
    ENV = os.getenv("ENVIRONMENT", Environment.DEVELOPMENT.value)
    DEBUG = ENV == Environment.DEVELOPMENT.value

    # Server
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8000"))
    WORKERS = int(os.getenv("WORKERS", "4" if ENV == Environment.PRODUCTION.value else "1"))

    # Database
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "crypto_signals")

    DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
    DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    SQL_ECHO = os.getenv("SQL_ECHO", "false").lower() == "true"

    @property
    def DATABASE_URL(self) -> str:
        """Construct database URL."""
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # External APIs
    BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
    BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")
    FEAR_GREED_API_KEY = os.getenv("FEAR_GREED_API_KEY", "")

    # Monitoring
    PROMETHEUS_ENABLED = os.getenv("PROMETHEUS_ENABLED", "true").lower() == "true"
    SENTRY_DSN = os.getenv("SENTRY_DSN", "")

    # Circuit Breaker
    CIRCUIT_BREAKER_FAILURE_THRESHOLD = int(os.getenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5"))
    CIRCUIT_BREAKER_TIMEOUT = int(os.getenv("CIRCUIT_BREAKER_TIMEOUT", "60"))

    # Rate Limiting
    RATE_LIMIT_SCAN = int(os.getenv("RATE_LIMIT_SCAN", "30"))
    RATE_LIMIT_SIGNAL = int(os.getenv("RATE_LIMIT_SIGNAL", "60"))
    RATE_LIMIT_CHART = int(os.getenv("RATE_LIMIT_CHART", "60"))
    RATE_LIMIT_MARKET = int(os.getenv("RATE_LIMIT_MARKET", "20"))

    # CORS
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

    # API Keys
    API_KEYS = os.getenv("API_KEYS", "demo-key-public:demo-user")

    # Redis (for future use)
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

    @classmethod
    def validate(cls) -> None:
        """Validate required configuration values."""
        errors = []

        # Check required database config
        if not cls.DB_HOST:
            errors.append("DB_HOST is required")
        if not cls.DB_NAME:
            errors.append("DB_NAME is required")

        # Check production-specific requirements
        if cls.ENV == Environment.PRODUCTION.value:
            if not cls.SENTRY_DSN:
                errors.append("SENTRY_DSN is required in production")
            if cls.CORS_ORIGINS == ["http://localhost:3000"]:
                errors.append("CORS_ORIGINS must be configured for production")

        if errors:
            raise ValueError(f"Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors))

    @classmethod
    def to_dict(cls) -> dict:
        """Export configuration as dictionary (for logging)."""
        return {
            "environment": cls.ENV,
            "debug": cls.DEBUG,
            "host": cls.HOST,
            "port": cls.PORT,
            "workers": cls.WORKERS,
            "database": cls.DB_NAME,
            "database_host": cls.DB_HOST,
            "log_level": cls.LOG_LEVEL,
            "prometheus_enabled": cls.PROMETHEUS_ENABLED,
            "circuit_breaker_threshold": cls.CIRCUIT_BREAKER_FAILURE_THRESHOLD,
        }


# Export singleton
config = Config()
