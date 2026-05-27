"""Database connection and session management."""

import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from models import Base
from logging_config import get_logger

logger = get_logger(__name__)

# Build database URL from environment
# Use SQLite for local development, PostgreSQL for production
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

if ENVIRONMENT == "production":
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "crypto_signals")
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
else:
    # Local development with SQLite
    DATABASE_URL = "sqlite:///./crypto_signals.db"

# Create engine
# Use NullPool for development/serverless; use QueuePool for production
engine_kwargs = {
    "echo": os.getenv("SQL_ECHO", "false").lower() == "true",
    "pool_pre_ping": True,  # Test connections before using
}

if ENVIRONMENT == "production":
    engine_kwargs.update({
        "pool_size": int(os.getenv("DB_POOL_SIZE", "5")),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "10")),
        "connect_args": {"connect_timeout": 10},
    })

engine = create_engine(DATABASE_URL, **engine_kwargs)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """Dependency injection for FastAPI routes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database: create all tables."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info(
            "Database initialized",
            action="database_initialized",
            tables=list(Base.metadata.tables.keys()),
        )
    except Exception as e:
        logger.error(
            f"Database initialization failed: {e}",
            action="database_init_failed",
            error=str(e),
            exc_info=True,
        )
        raise


def drop_db():
    """Drop all tables. USE WITH CAUTION - development only."""
    try:
        Base.metadata.drop_all(bind=engine)
        logger.warning("Database dropped - DEVELOPMENT ONLY", action="database_dropped")
    except Exception as e:
        logger.error(
            f"Database drop failed: {e}",
            action="database_drop_failed",
            error=str(e),
            exc_info=True,
        )
        raise


def health_check() -> bool:
    """Check if database connection is healthy."""
    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception as e:
        logger.warning(
            "Database health check failed",
            action="database_health_check_failed",
            error=str(e),
        )
        return False
