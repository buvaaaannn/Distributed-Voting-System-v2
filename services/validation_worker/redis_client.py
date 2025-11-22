"""Redis client for validation worker."""

import redis
import logging
from typing import Optional
from config import Config

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis client for hash validation and duplicate checking."""

    def __init__(self):
        """Initialize Redis connection pool."""
        self.pool = redis.ConnectionPool(
            host=Config.REDIS_HOST,
            port=Config.REDIS_PORT,
            db=Config.REDIS_DB,
            password=Config.REDIS_PASSWORD,
            max_connections=Config.REDIS_MAX_CONNECTIONS,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_keepalive=True,
            health_check_interval=30
        )
        self.client = redis.Redis(connection_pool=self.pool)
        self._test_connection()

    def _test_connection(self):
        """Test Redis connection on initialization."""
        try:
            self.client.ping()
            logger.info("Redis connection established successfully")
        except redis.RedisError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    def check_valid_hash(self, hash_value: str) -> bool:
        """
        Check if hash exists in the valid_hashes set.

        Args:
            hash_value: The hash to check

        Returns:
            True if hash is valid, False otherwise
        """
        try:
            result = self.client.sismember('valid_hashes', hash_value)
            logger.debug(f"Hash {hash_value} valid check: {result}")
            return bool(result)
        except redis.RedisError as e:
            logger.error(f"Redis error checking valid hash: {e}")
            raise

    def check_duplicate(self, hash_value: str) -> bool:
        """
        Check if hash has already voted (exists in voted_hashes set).

        Args:
            hash_value: The hash to check

        Returns:
            True if hash already voted (duplicate), False otherwise
        """
        try:
            result = self.client.sismember('voted_hashes', hash_value)
            logger.debug(f"Hash {hash_value} duplicate check: {result}")
            return bool(result)
        except redis.RedisError as e:
            logger.error(f"Redis error checking duplicate: {e}")
            raise

    def mark_as_voted(self, hash_value: str) -> None:
        """
        Mark hash as voted by adding to voted_hashes set.

        Args:
            hash_value: The hash to mark as voted
        """
        try:
            self.client.sadd('voted_hashes', hash_value)
            logger.debug(f"Hash {hash_value} marked as voted")
        except redis.RedisError as e:
            logger.error(f"Redis error marking as voted: {e}")
            raise

    def increment_duplicate_count(self, hash_value: str) -> int:
        """
        Increment duplicate attempt counter for a hash.

        Args:
            hash_value: The hash to increment counter for

        Returns:
            The new count value
        """
        try:
            count = self.client.incr(f'duplicate_count:{hash_value}')
            logger.debug(f"Hash {hash_value} duplicate count: {count}")
            return count
        except redis.RedisError as e:
            logger.error(f"Redis error incrementing duplicate count: {e}")
            raise

    def get_duplicate_count(self, hash_value: str) -> int:
        """
        Get current duplicate attempt count for a hash.

        Args:
            hash_value: The hash to get count for

        Returns:
            The current count (0 if not found)
        """
        try:
            count = self.client.get(f'duplicate_count:{hash_value}')
            return int(count) if count else 0
        except redis.RedisError as e:
            logger.error(f"Redis error getting duplicate count: {e}")
            raise

    def close(self):
        """Close Redis connection pool."""
        try:
            self.pool.disconnect()
            logger.info("Redis connection pool closed")
        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}")
