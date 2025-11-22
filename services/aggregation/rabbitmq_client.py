"""
Async RabbitMQ consumer client for vote aggregation using aio-pika.
"""
import logging
import asyncio
from typing import Callable, Optional
import aio_pika
from aio_pika import connect_robust, Message, DeliveryMode
from aio_pika.abc import AbstractIncomingMessage

from config import config

logger = logging.getLogger(__name__)


class RabbitMQClient:
    """Async RabbitMQ consumer with auto-reconnect capability."""

    def __init__(self, queue_name: str = None):
        """
        Initialize RabbitMQ client.

        Args:
            queue_name: Name of the queue to consume from.
        """
        self.queue_name = queue_name or config.RABBITMQ_QUEUE
        self.connection = None
        self.channel = None
        self.queue = None
        self.consumer_tag = None

    async def connect(self) -> bool:
        """
        Establish connection to RabbitMQ.

        Returns:
            True if connection successful, False otherwise.
        """
        try:
            # Build connection URL
            url = f"amqp://{config.RABBITMQ_USER}:{config.RABBITMQ_PASSWORD}@{config.RABBITMQ_HOST}:{config.RABBITMQ_PORT}/"

            # Connect with robust connection (auto-reconnect)
            self.connection = await connect_robust(
                url,
                heartbeat=600,  # 10 minutes
                client_properties={
                    'connection_name': f'aggregator-{config.RABBITMQ_QUEUE}'
                }
            )

            # Create channel
            self.channel = await self.connection.channel()

            # Set QoS (prefetch count)
            await self.channel.set_qos(prefetch_count=config.RABBITMQ_PREFETCH_COUNT)

            # Declare queue (idempotent)
            self.queue = await self.channel.declare_queue(
                self.queue_name,
                durable=True,
                arguments={
                    'x-message-ttl': 86400000,  # 24 hours
                    'x-max-length': 1000000
                }
            )

            logger.info(
                f"Connected to RabbitMQ: {config.RABBITMQ_HOST}:{config.RABBITMQ_PORT}, "
                f"Queue: {self.queue_name}, Prefetch: {config.RABBITMQ_PREFETCH_COUNT}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            return False

    async def consume(self, callback: Callable, auto_ack: bool = False):
        """
        Start consuming messages from the queue.

        Args:
            callback: Async function to call for each message.
                      Signature: async callback(message: AbstractIncomingMessage)
            auto_ack: Whether to automatically acknowledge messages.
        """
        if not self.connection or not self.queue:
            if not await self.connect():
                raise RuntimeError("Failed to connect to RabbitMQ")

        try:
            logger.info(f"Starting to consume from queue: {self.queue_name}")

            # Start consuming
            async with self.queue.iterator() as queue_iter:
                async for message in queue_iter:
                    try:
                        # Call the callback
                        await callback(message)

                        # Acknowledge if not auto-ack
                        if not auto_ack and not message.processed:
                            await message.ack()

                    except Exception as e:
                        logger.error(f"Error processing message: {e}", exc_info=True)
                        # Reject and requeue on error
                        if not message.processed:
                            await message.nack(requeue=True)

        except asyncio.CancelledError:
            logger.info("Consumer cancelled, shutting down gracefully")
            raise
        except Exception as e:
            logger.error(f"Error in consume loop: {e}", exc_info=True)
            raise

    async def close(self):
        """Close RabbitMQ connection."""
        try:
            if self.channel and not self.channel.is_closed:
                await self.channel.close()
                logger.debug("Channel closed")

            if self.connection and not self.connection.is_closed:
                await self.connection.close()
                logger.info("RabbitMQ connection closed")

        except Exception as e:
            logger.error(f"Error closing RabbitMQ connection: {e}")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
