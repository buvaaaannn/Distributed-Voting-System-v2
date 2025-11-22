"""Configuration management for validation worker service."""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configuration class for validation worker."""

    # RabbitMQ Configuration
    RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
    RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', '5672'))
    RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'guest')
    RABBITMQ_PASS = os.getenv('RABBITMQ_PASS', 'guest')
    RABBITMQ_VHOST = os.getenv('RABBITMQ_VHOST', '/')

    # Queue names
    VALIDATION_QUEUE = os.getenv('VALIDATION_QUEUE', 'votes.validation')
    AGGREGATION_QUEUE = os.getenv('AGGREGATION_QUEUE', 'votes.aggregation')
    REVIEW_QUEUE = os.getenv('REVIEW_QUEUE', 'votes.review')

    # Redis Configuration
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
    REDIS_DB = int(os.getenv('REDIS_DB', '0'))
    REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None)
    REDIS_MAX_CONNECTIONS = int(os.getenv('REDIS_MAX_CONNECTIONS', '50'))

    # PostgreSQL Configuration
    POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
    POSTGRES_PORT = int(os.getenv('POSTGRES_PORT', '5432'))
    POSTGRES_DB = os.getenv('POSTGRES_DB', 'election_db')
    POSTGRES_USER = os.getenv('POSTGRES_USER', 'postgres')
    POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'postgres')
    POSTGRES_MIN_POOL_SIZE = int(os.getenv('POSTGRES_MIN_POOL_SIZE', '2'))
    POSTGRES_MAX_POOL_SIZE = int(os.getenv('POSTGRES_MAX_POOL_SIZE', '10'))

    # Prometheus Metrics
    METRICS_PORT = int(os.getenv('METRICS_PORT', '8001'))

    # Worker Configuration
    PREFETCH_COUNT = int(os.getenv('PREFETCH_COUNT', '10'))
    WORKER_ID = os.getenv('WORKER_ID', 'worker-1')

    # Retry Configuration
    MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
    RETRY_DELAY = int(os.getenv('RETRY_DELAY', '5'))

    @classmethod
    def get_rabbitmq_url(cls):
        """Get RabbitMQ connection URL."""
        return f"amqp://{cls.RABBITMQ_USER}:{cls.RABBITMQ_PASS}@{cls.RABBITMQ_HOST}:{cls.RABBITMQ_PORT}/{cls.RABBITMQ_VHOST}"

    @classmethod
    def get_postgres_dsn(cls):
        """Get PostgreSQL connection DSN."""
        return f"host={cls.POSTGRES_HOST} port={cls.POSTGRES_PORT} dbname={cls.POSTGRES_DB} user={cls.POSTGRES_USER} password={cls.POSTGRES_PASSWORD}"
