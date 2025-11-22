"""Configuration management for the Ingestion API service."""
import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Service configuration
    SERVICE_NAME: str = "ingestion-api"
    API_VERSION: str = "v1"
    DEBUG: bool = False

    # Server configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # RabbitMQ configuration
    RABBITMQ_HOST: str = "rabbitmq"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "guest"
    RABBITMQ_PASSWORD: str = "guest"
    RABBITMQ_EXCHANGE: str = "votes.exchange"
    RABBITMQ_ROUTING_KEY: str = "vote.submitted"

    # PostgreSQL configuration
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "election_db"
    POSTGRES_USER: str = "election_user"
    POSTGRES_PASSWORD: str = "election_pass"

    # Redis configuration
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None

    # Rate limiting
    RATE_LIMIT: str = "100000/second"

    # CORS settings
    CORS_ORIGINS: list = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list = ["*"]
    CORS_ALLOW_HEADERS: list = ["*"]

    # Connection pools
    POSTGRES_POOL_MIN_SIZE: int = 10
    POSTGRES_POOL_MAX_SIZE: int = 20
    RABBITMQ_POOL_SIZE: int = 10

    class Config:
        env_file = ".env"
        case_sensitive = True

    @property
    def postgres_dsn(self) -> str:
        """Generate PostgreSQL connection string."""
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def rabbitmq_url(self) -> str:
        """Generate RabbitMQ connection URL."""
        return (
            f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASSWORD}"
            f"@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/"
        )

    @property
    def redis_url(self) -> str:
        """Generate Redis connection URL."""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


settings = Settings()
