"""Application settings loaded from environment variables / .env file."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database — defaults to SQLite for local development
    DATABASE_URL: str = "sqlite:///./sales_analytics.db"

    # JWT configuration
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Redis URL for rate limiting — "memory://" uses in-memory storage
    REDIS_URL: str = "memory://"

    # CORS configuration
    CORS_ORIGINS: list[str] = ["*"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
