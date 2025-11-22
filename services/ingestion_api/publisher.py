"""RabbitMQ publisher for vote events."""
import json
import asyncio
from typing import Optional
from datetime import datetime
import aio_pika
from aio_pika import connect_robust, Message, DeliveryMode
from aio_pika.pool import Pool
import logging

from config import settings

logger = logging.getLogger(__name__)


class RabbitMQPublisher:
    """Async RabbitMQ publisher with connection pooling."""

    def __init__(self):
        self.connection_pool: Optional[Pool] = None
        self.channel_pool: Optional[Pool] = None
        self.exchange: Optional[aio_pika.Exchange] = None

    async def get_connection(self) -> aio_pika.Connection:
        """Get a connection from the pool."""
        return await connect_robust(settings.rabbitmq_url)

    async def get_channel(self) -> aio_pika.Channel:
        """Get a channel from the pool."""
        async with self.connection_pool.acquire() as connection:
            return await connection.channel()

    async def initialize(self):
        """Initialize connection and channel pools."""
        try:
            # Create connection pool
            self.connection_pool = Pool(
                self.get_connection,
                max_size=settings.RABBITMQ_POOL_SIZE
            )

            # Create channel pool
            self.channel_pool = Pool(
                self.get_channel,
                max_size=settings.RABBITMQ_POOL_SIZE
            )

            # Declare exchange
            async with self.channel_pool.acquire() as channel:
                self.exchange = await channel.declare_exchange(
                    settings.RABBITMQ_EXCHANGE,
                    aio_pika.ExchangeType.TOPIC,
                    durable=True
                )

            logger.info("RabbitMQ publisher initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize RabbitMQ publisher: {e}")
            raise

    async def publish_vote(self, vote_data: dict) -> bool:
        """
        Publish vote data to RabbitMQ.

        Args:
            vote_data: Dictionary containing vote information

        Returns:
            bool: True if published successfully, False otherwise
        """
        try:
            async with self.channel_pool.acquire() as channel:
                exchange = await channel.get_exchange(settings.RABBITMQ_EXCHANGE)

                # Add timestamp (matches validation worker expectation)
                vote_data["vote_timestamp"] = datetime.utcnow().isoformat()

                # Create message
                message = Message(
                    body=json.dumps(vote_data).encode(),
                    delivery_mode=DeliveryMode.PERSISTENT,
                    content_type="application/json",
                    timestamp=datetime.utcnow()
                )

                # Publish to exchange
                await exchange.publish(
                    message,
                    routing_key=settings.RABBITMQ_ROUTING_KEY
                )

                logger.info(
                    f"Published vote to RabbitMQ: "
                    f"hash={vote_data.get('hash')}, "
                    f"law_id={vote_data.get('law_id')}"
                )
                return True

        except Exception as e:
            logger.error(f"Failed to publish vote to RabbitMQ: {e}")
            return False

    async def check_health(self) -> bool:
        """
        Check RabbitMQ connection health.

        Returns:
            bool: True if healthy, False otherwise
        """
        try:
            async with self.channel_pool.acquire() as channel:
                # Try to declare a temporary queue to verify connection
                await channel.declare_queue("health_check", auto_delete=True)
                return True
        except Exception as e:
            logger.error(f"RabbitMQ health check failed: {e}")
            return False

    async def close(self):
        """Close all connections and channels."""
        try:
            if self.channel_pool:
                await self.channel_pool.close()
            if self.connection_pool:
                await self.connection_pool.close()
            logger.info("RabbitMQ publisher closed successfully")
        except Exception as e:
            logger.error(f"Error closing RabbitMQ publisher: {e}")


# Global publisher instance
publisher = RabbitMQPublisher()
