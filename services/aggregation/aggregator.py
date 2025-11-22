"""
Async aggregation service for vote counting.

Consumes votes from RabbitMQ, batches them, and updates PostgreSQL.
"""
import logging
import signal
import sys
import json
import time
import asyncio
from datetime import datetime
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor
from prometheus_client import Counter, Gauge, start_http_server
from aio_pika.abc import AbstractIncomingMessage

from config import config
from database import Database, DatabaseError
from rabbitmq_client import RabbitMQClient

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Prometheus metrics
votes_aggregated_total = Counter(
    'votes_aggregated_total',
    'Total number of votes aggregated',
    ['law_id', 'choice']
)

current_vote_totals = Gauge(
    'current_vote_totals',
    'Current vote totals',
    ['law_id', 'choice']
)

batch_processing_duration = Gauge(
    'batch_processing_duration_seconds',
    'Time taken to process a batch of votes'
)

batch_size_processed = Counter(
    'batch_size_processed_total',
    'Total size of batches processed'
)

aggregation_errors = Counter(
    'aggregation_errors_total',
    'Total number of aggregation errors',
    ['error_type']
)


class VoteAggregator:
    """Async vote aggregation service."""

    def __init__(self):
        """Initialize the aggregator."""
        self.database = Database()
        self.rabbitmq = RabbitMQClient()
        self.running = True

        # Batching
        self.current_batch: List[Dict] = []
        self.batch_lock = asyncio.Lock()
        self.last_batch_time = time.time()

        # Thread pool for database operations
        self.executor = ThreadPoolExecutor(max_workers=4)

        # Signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.running = False

    async def start(self):
        """Start the aggregation service."""
        try:
            # Start Prometheus metrics server
            logger.info(f"Starting Prometheus metrics server on port {config.PROMETHEUS_PORT}")
            start_http_server(config.PROMETHEUS_PORT)

            # Load initial vote counts into Prometheus
            await self._sync_vote_counts_to_prometheus()

            # Start batch processor task
            batch_task = asyncio.create_task(self._batch_processor_loop())

            # Start consuming from RabbitMQ
            logger.info("Starting RabbitMQ consumer...")
            try:
                await self.rabbitmq.consume(callback=self._on_message, auto_ack=False)
            except asyncio.CancelledError:
                logger.info("Consumer cancelled")

            # Wait for batch processor to complete
            batch_task.cancel()
            try:
                await batch_task
            except asyncio.CancelledError:
                pass

        except Exception as e:
            logger.error(f"Failed to start aggregator: {e}", exc_info=True)
            await self.shutdown()
            sys.exit(1)

    async def _on_message(self, message: AbstractIncomingMessage):
        """
        Callback for RabbitMQ messages.

        Args:
            message: Incoming message from RabbitMQ
        """
        try:
            # Parse message
            vote = json.loads(message.body.decode())
            logger.debug(f"Received vote: law_id={vote.get('law_id')}, vote={vote.get('vote')}")

            # Add to batch
            async with self.batch_lock:
                self.current_batch.append(vote)

                # Check if batch is full
                if len(self.current_batch) >= config.BATCH_SIZE:
                    logger.info(f"Batch size reached ({config.BATCH_SIZE}), processing batch")
                    await self._process_batch()

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode message: {e}")
            aggregation_errors.labels(error_type='json_decode').inc()
            # Reject malformed message (don't requeue)
            await message.reject(requeue=False)

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            aggregation_errors.labels(error_type='processing').inc()
            # Requeue on unexpected error
            await message.nack(requeue=True)

    async def _batch_processor_loop(self):
        """Background task to process batches on timeout."""
        while self.running:
            try:
                await asyncio.sleep(0.1)  # Check every 100ms

                async with self.batch_lock:
                    # Check if batch timeout has elapsed
                    if (self.current_batch and
                        time.time() - self.last_batch_time >= config.BATCH_TIMEOUT_SECONDS):

                        logger.info(
                            f"Batch timeout reached ({config.BATCH_TIMEOUT_SECONDS}s), "
                            f"processing {len(self.current_batch)} votes"
                        )
                        await self._process_batch()

            except Exception as e:
                logger.error(f"Error in batch processor loop: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def _process_batch(self):
        """
        Process the current batch.

        Note: This method should be called with batch_lock already held!
        """
        if not self.current_batch:
            return

        batch_start_time = time.time()
        batch_size = len(self.current_batch)
        batch_to_process = self.current_batch.copy()

        logger.info(f"Processing batch of {batch_size} votes")

        # Run database operation in executor (so it doesn't block the event loop)
        loop = asyncio.get_event_loop()
        try:
            success_count, failure_count = await loop.run_in_executor(
                self.executor,
                self.database.batch_update_results,
                batch_to_process
            )

            # Update Prometheus metrics
            for vote in batch_to_process:
                law_id = vote.get('law_id', 'unknown')
                choice = vote.get('vote', 'unknown').lower()
                votes_aggregated_total.labels(law_id=law_id, choice=choice).inc()

            # Sync current totals to Prometheus
            await self._sync_vote_counts_to_prometheus()

            # Update batch metrics
            batch_duration = time.time() - batch_start_time
            batch_processing_duration.set(batch_duration)
            batch_size_processed.inc(batch_size)

            logger.info(
                f"Batch processed successfully: {batch_size} votes, "
                f"duration: {batch_duration:.3f}s"
            )

            # Clear batch
            self.current_batch = []
            self.last_batch_time = time.time()

        except DatabaseError as e:
            logger.error(f"Database error processing batch: {e}")
            aggregation_errors.labels(error_type='database').inc()
            # Don't clear batch on database error - will retry on next timeout
            raise

        except Exception as e:
            logger.error(f"Unexpected error processing batch: {e}", exc_info=True)
            aggregation_errors.labels(error_type='unexpected').inc()
            raise

    async def _sync_vote_counts_to_prometheus(self):
        """Sync current vote counts from database to Prometheus gauges."""
        try:
            loop = asyncio.get_event_loop()
            vote_counts = await loop.run_in_executor(
                self.executor,
                self.database.get_all_vote_counts
            )

            for law_id, counts in vote_counts.items():
                current_vote_totals.labels(law_id=law_id, choice='oui').set(counts.get('oui', 0))
                current_vote_totals.labels(law_id=law_id, choice='non').set(counts.get('non', 0))

        except Exception as e:
            logger.error(f"Error syncing vote counts to Prometheus: {e}")

    async def shutdown(self):
        """Graceful shutdown."""
        logger.info("Shutting down aggregator...")
        self.running = False

        # Process final batch
        async with self.batch_lock:
            if self.current_batch:
                logger.info(f"Processing final batch of {len(self.current_batch)} votes")
                try:
                    await self._process_batch()
                except Exception as e:
                    logger.error(f"Error processing final batch: {e}")

        # Close RabbitMQ connection
        await self.rabbitmq.close()

        # Shutdown executor
        self.executor.shutdown(wait=True)

        logger.info("Aggregator shutdown complete")


async def main():
    """Main entry point."""
    logger.info("="*60)
    logger.info("Starting Vote Aggregation Service (ASYNC)")
    logger.info(f"RabbitMQ: {config.RABBITMQ_HOST}:{config.RABBITMQ_PORT}")
    logger.info(f"Queue: {config.RABBITMQ_QUEUE}")
    logger.info(f"Batch Size: {config.BATCH_SIZE}")
    logger.info(f"Batch Timeout: {config.BATCH_TIMEOUT_SECONDS}s")
    logger.info(f"Prefetch Count: {config.RABBITMQ_PREFETCH_COUNT}")
    logger.info("="*60)

    aggregator = VoteAggregator()

    try:
        await aggregator.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        await aggregator.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
