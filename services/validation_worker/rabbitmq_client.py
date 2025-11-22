"""RabbitMQ client for validation worker."""

import pika
import json
import logging
import time
from typing import Callable, Optional, Dict, Any
from config import Config

logger = logging.getLogger(__name__)


class RabbitMQClient:
    """RabbitMQ client for consuming and publishing messages."""

    def __init__(self):
        """Initialize RabbitMQ client."""
        self.connection = None
        self.channel = None
        self.consuming = False
        self._connect()

    def _connect(self):
        """Establish connection to RabbitMQ."""
        max_retries = 5
        retry_delay = 5

        for attempt in range(max_retries):
            try:
                parameters = pika.ConnectionParameters(
                    host=Config.RABBITMQ_HOST,
                    port=Config.RABBITMQ_PORT,
                    virtual_host=Config.RABBITMQ_VHOST,
                    credentials=pika.PlainCredentials(
                        Config.RABBITMQ_USER,
                        Config.RABBITMQ_PASS
                    ),
                    heartbeat=600,
                    blocked_connection_timeout=300,
                    connection_attempts=3,
                    retry_delay=2
                )

                self.connection = pika.BlockingConnection(parameters)
                self.channel = self.connection.channel()

                # Set QoS - prefetch count
                self.channel.basic_qos(prefetch_count=Config.PREFETCH_COUNT)

                # Declare queues (idempotent)
                self._declare_queues()

                logger.info("RabbitMQ connection established successfully")
                return

            except pika.exceptions.AMQPConnectionError as e:
                logger.warning(f"Connection attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    logger.error("Failed to connect to RabbitMQ after all retries")
                    raise

    def _declare_queues(self):
        """Declare all required queues."""
        queues = [
            Config.VALIDATION_QUEUE,
            Config.REVIEW_QUEUE
        ]

        for queue in queues:
            self.channel.queue_declare(
                queue=queue,
                durable=True,
                arguments={
                    'x-message-ttl': 86400000,  # 24 hours
                    'x-max-length': 1000000
                }
            )
            logger.debug(f"Queue declared: {queue}")

    def consume(self, queue: str, callback: Callable):
        """
        Start consuming messages from a queue.

        Args:
            queue: Queue name to consume from
            callback: Callback function to process messages
        """
        try:
            self.consuming = True
            logger.info(f"Starting to consume from queue: {queue}")

            self.channel.basic_consume(
                queue=queue,
                on_message_callback=callback,
                auto_ack=False
            )

            self.channel.start_consuming()

        except KeyboardInterrupt:
            logger.info("Consumption interrupted by user")
            self.stop_consuming()
        except Exception as e:
            logger.error(f"Error during consumption: {e}")
            raise

    def stop_consuming(self):
        """Stop consuming messages."""
        if self.consuming and self.channel:
            logger.info("Stopping message consumption")
            self.channel.stop_consuming()
            self.consuming = False

    def publish(
        self,
        queue: str,
        message: Dict[str, Any],
        priority: int = 0
    ):
        """
        Publish a message to a queue.

        Args:
            queue: Queue name to publish to
            message: Message dictionary to publish
            priority: Message priority (0-9)
        """
        try:
            # Ensure connection is alive
            if not self.connection or self.connection.is_closed:
                logger.warning("Connection lost, reconnecting...")
                self._connect()

            self.channel.basic_publish(
                exchange='',
                routing_key=queue,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Persistent
                    priority=priority,
                    content_type='application/json'
                )
            )

            logger.debug(f"Published message to {queue}: {message}")

        except Exception as e:
            logger.error(f"Error publishing message to {queue}: {e}")
            raise

    def ack(self, delivery_tag: int):
        """
        Acknowledge a message.

        Args:
            delivery_tag: Message delivery tag
        """
        try:
            self.channel.basic_ack(delivery_tag=delivery_tag)
            logger.debug(f"Message acknowledged: {delivery_tag}")
        except Exception as e:
            logger.error(f"Error acknowledging message: {e}")
            raise

    def nack(self, delivery_tag: int, requeue: bool = True):
        """
        Negative acknowledge a message.

        Args:
            delivery_tag: Message delivery tag
            requeue: Whether to requeue the message
        """
        try:
            self.channel.basic_nack(
                delivery_tag=delivery_tag,
                requeue=requeue
            )
            logger.debug(f"Message nacked: {delivery_tag}, requeue: {requeue}")
        except Exception as e:
            logger.error(f"Error nacking message: {e}")
            raise

    def reject(self, delivery_tag: int, requeue: bool = False):
        """
        Reject a message.

        Args:
            delivery_tag: Message delivery tag
            requeue: Whether to requeue the message
        """
        try:
            self.channel.basic_reject(
                delivery_tag=delivery_tag,
                requeue=requeue
            )
            logger.debug(f"Message rejected: {delivery_tag}, requeue: {requeue}")
        except Exception as e:
            logger.error(f"Error rejecting message: {e}")
            raise

    def get_queue_size(self, queue: str) -> int:
        """
        Get the number of messages in a queue.

        Args:
            queue: Queue name

        Returns:
            Number of messages in queue
        """
        try:
            result = self.channel.queue_declare(
                queue=queue,
                durable=True,
                passive=True
            )
            return result.method.message_count
        except Exception as e:
            logger.error(f"Error getting queue size for {queue}: {e}")
            return 0

    def close(self):
        """Close RabbitMQ connection."""
        try:
            if self.consuming:
                self.stop_consuming()

            if self.connection and not self.connection.is_closed:
                self.connection.close()
                logger.info("RabbitMQ connection closed")
        except Exception as e:
            logger.error(f"Error closing RabbitMQ connection: {e}")
