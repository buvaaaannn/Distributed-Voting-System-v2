"""
Configuration module for the aggregation service.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration."""

    # RabbitMQ Configuration
    RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
    RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', '5672'))
    RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'guest')
    RABBITMQ_PASSWORD = os.getenv('RABBITMQ_PASSWORD', 'guest')
    RABBITMQ_QUEUE = os.getenv('RABBITMQ_QUEUE', 'votes.aggregation')
    RABBITMQ_PREFETCH_COUNT = int(os.getenv('RABBITMQ_PREFETCH_COUNT', '100'))

    # PostgreSQL Configuration
    POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
    POSTGRES_PORT = int(os.getenv('POSTGRES_PORT', '5432'))
    POSTGRES_DB = os.getenv('POSTGRES_DB', 'election_votes')
    POSTGRES_USER = os.getenv('POSTGRES_USER', 'postgres')
    POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'postgres')
    POSTGRES_MIN_CONNECTIONS = int(os.getenv('POSTGRES_MIN_CONNECTIONS', '2'))
    POSTGRES_MAX_CONNECTIONS = int(os.getenv('POSTGRES_MAX_CONNECTIONS', '10'))

    # Batching Configuration
    BATCH_SIZE = int(os.getenv('BATCH_SIZE', '100'))
    BATCH_TIMEOUT_SECONDS = float(os.getenv('BATCH_TIMEOUT_SECONDS', '1.0'))

    # Retry Configuration
    MAX_RETRY_ATTEMPTS = int(os.getenv('MAX_RETRY_ATTEMPTS', '3'))
    RETRY_DELAY_SECONDS = float(os.getenv('RETRY_DELAY_SECONDS', '1.0'))

    # Prometheus Configuration
    PROMETHEUS_PORT = int(os.getenv('PROMETHEUS_PORT', '8001'))

    # Logging Configuration
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')


config = Config()
