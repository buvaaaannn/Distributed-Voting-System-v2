"""
Main validation worker service.

Author: David Marleau
Project: Distributed Voting System - Demo Version

╔══════════════════════════════════════════════════════════════════════════════╗
║                         DDoS PROTECTION MECHANISMS                           ║
╚══════════════════════════════════════════════════════════════════════════════╝

This worker implements several anti-DDoS measures to prevent resource exhaustion:

1. PAYLOAD SIZE LIMITS (Line ~140)
   - Max message size: 1KB
   - Rejects oversized payloads immediately
   - Prevents memory exhaustion attacks

2. DUPLICATE VOTE HANDLING (Line ~200)
   - Duplicates are DROPPED (not queued)
   - Only increments Redis counter: duplicate_count:{hash}
   - No database writes, no queue accumulation
   - Prevents queue overflow from repeated votes

3. ERROR PATTERN GROUPING (Line ~160)
   - Groups similar invalid hashes by pattern (first 8 chars)
   - Only logs NEW error patterns to review queue
   - Known patterns just increment counter: error_pattern:{pattern}
   - Prevents log spam from random gibberish attacks

4. RATE LIMITING
   - Review queue only receives UNIQUE error patterns
   - Duplicate errors and votes are counted, not stored
   - Audit trail via Prometheus metrics, not queue accumulation

════════════════════════════════════════════════════════════════════════════════
"""

import signal
import sys
import json
import logging
import time
from datetime import datetime
from typing import Dict, Any
from prometheus_client import Counter, Histogram, Gauge, start_http_server

from config import Config
from redis_client import RedisClient
from rabbitmq_client import RabbitMQClient
from database import DatabaseClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Prometheus metrics
votes_processed = Counter(
    'validation_votes_processed_total',
    'Total number of votes processed',
    ['status']
)

validation_latency = Histogram(
    'validation_processing_latency_seconds',
    'Time spent processing validation',
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
)

validation_errors = Counter(
    'validation_errors_total',
    'Total number of validation errors',
    ['error_type']
)

queue_size = Gauge(
    'validation_queue_size',
    'Current size of validation queue'
)

redis_operations = Counter(
    'redis_operations_total',
    'Total Redis operations',
    ['operation', 'status']
)

db_operations = Counter(
    'database_operations_total',
    'Total database operations',
    ['operation', 'status']
)

# DDoS Protection Metrics
duplicate_attempts_total = Counter(
    'duplicate_attempts_total',
    'Total duplicate vote attempts (dropped, not queued)'
)

error_patterns_unique = Gauge(
    'error_patterns_unique_total',
    'Total unique error patterns seen'
)

error_patterns_repeated = Counter(
    'error_patterns_repeated_total',
    'Total repeated error patterns (dropped, not queued)'
)

oversized_payloads = Counter(
    'oversized_payloads_total',
    'Total oversized payloads rejected'
)


class ValidationWorker:
    """Main validation worker class."""

    def __init__(self):
        """Initialize the validation worker."""
        self.redis_client = None
        self.rabbitmq_client = None
        self.db_client = None
        self.shutdown_requested = False

        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

        logger.info(f"Initializing validation worker: {Config.WORKER_ID}")

    def _handle_shutdown(self, signum, frame):
        """Handle graceful shutdown on SIGTERM/SIGINT."""
        logger.info(f"Shutdown signal received: {signum}")
        self.shutdown_requested = True

        if self.rabbitmq_client:
            self.rabbitmq_client.stop_consuming()

    def initialize_clients(self):
        """Initialize all client connections."""
        try:
            logger.info("Initializing Redis client...")
            self.redis_client = RedisClient()

            logger.info("Initializing RabbitMQ client...")
            self.rabbitmq_client = RabbitMQClient()

            logger.info("Initializing Database client...")
            self.db_client = DatabaseClient()

            logger.info("All clients initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize clients: {e}")
            raise

    def process_vote(self, ch, method, properties, body):
        """
        Process a vote message from the validation queue.

        Args:
            ch: Channel
            method: Method
            properties: Properties
            body: Message body
        """
        start_time = time.time()
        vote_data = None

        try:
            # ═══════════════════════════════════════════════════════════════
            # DDoS PROTECTION #1: PAYLOAD SIZE LIMIT
            # ═══════════════════════════════════════════════════════════════
            # Reject oversized payloads immediately (max 1KB)
            MAX_PAYLOAD_SIZE = 1024  # 1KB
            if len(body) > MAX_PAYLOAD_SIZE:
                logger.warning(f"Oversized payload rejected: {len(body)} bytes (max {MAX_PAYLOAD_SIZE})")
                oversized_payloads.inc()
                self.rabbitmq_client.reject(method.delivery_tag, requeue=False)
                return

            # Parse message
            vote_data = json.loads(body)
            voter_hash = vote_data.get('hash')  # Use the hash field generated by API
            law_id = vote_data.get('law_id')
            vote = vote_data.get('vote')
            vote_timestamp_str = vote_data.get('vote_timestamp')

            logger.info(f"Processing vote: hash={voter_hash}, law_id={law_id}, vote={vote}")

            # Validate required fields
            if not voter_hash or not law_id or not vote:
                logger.error(f"Invalid vote data: missing required fields")
                validation_errors.labels(error_type='invalid_format').inc()
                self.rabbitmq_client.reject(method.delivery_tag, requeue=False)
                return

            # Parse timestamp
            vote_timestamp = datetime.fromisoformat(vote_timestamp_str.replace('Z', '+00:00'))

            # Step 1: Check if hash is valid
            try:
                is_valid = self.redis_client.check_valid_hash(voter_hash)
                redis_operations.labels(operation='check_valid', status='success').inc()
            except Exception as e:
                logger.error(f"Redis error checking valid hash: {e}")
                redis_operations.labels(operation='check_valid', status='error').inc()
                validation_errors.labels(error_type='redis_error').inc()
                self.rabbitmq_client.nack(method.delivery_tag, requeue=True)
                return

            if not is_valid:
                # ═══════════════════════════════════════════════════════════════
                # DDoS PROTECTION #2: ERROR PATTERN GROUPING
                # ═══════════════════════════════════════════════════════════════
                # Group similar invalid hashes to prevent log spam from random gibberish
                # Only log NEW error patterns to review queue

                logger.warning(f"Invalid hash detected: {voter_hash}")

                # Create error pattern (first 8 chars to group similar errors)
                error_pattern = voter_hash[:8] if voter_hash else "unknown"
                pattern_key = f"error_pattern:{error_pattern}"

                # Check if this error pattern is new
                try:
                    is_new_pattern = self.redis_client.client.sadd('error_patterns_seen', error_pattern)

                    if is_new_pattern:
                        # NEW error pattern - log to review queue for investigation
                        logger.info(f"NEW error pattern detected: {error_pattern}")
                        error_patterns_unique.inc()

                        review_message = {
                            'voter_hash': voter_hash,
                            'error_pattern': error_pattern,
                            'law_id': law_id,
                            'vote': vote,
                            'vote_timestamp': vote_timestamp_str,
                            'status': 'invalid',
                            'reason': 'Hash not found in valid_hashes set',
                            'processed_timestamp': datetime.utcnow().isoformat()
                        }

                        self.rabbitmq_client.publish(Config.REVIEW_QUEUE, review_message)
                    else:
                        # KNOWN error pattern - just increment counter, DROP (don't queue)
                        count = self.redis_client.client.incr(pattern_key)
                        error_patterns_repeated.inc()
                        logger.debug(f"Known error pattern {error_pattern}: {count} occurrences (dropped)")

                except Exception as e:
                    logger.error(f"Redis error handling error pattern: {e}")
                    # Fallback: publish to review queue
                    review_message = {
                        'voter_hash': voter_hash,
                        'law_id': law_id,
                        'vote': vote,
                        'vote_timestamp': vote_timestamp_str,
                        'status': 'invalid',
                        'reason': 'Hash not found in valid_hashes set',
                        'processed_timestamp': datetime.utcnow().isoformat()
                    }
                    self.rabbitmq_client.publish(Config.REVIEW_QUEUE, review_message)

                votes_processed.labels(status='invalid').inc()

                # ACK the message
                self.rabbitmq_client.ack(method.delivery_tag)

                # Record latency
                validation_latency.observe(time.time() - start_time)
                return

            # Step 2: Check for duplicates
            try:
                is_duplicate = self.redis_client.check_duplicate(voter_hash)
                redis_operations.labels(operation='check_duplicate', status='success').inc()
            except Exception as e:
                logger.error(f"Redis error checking duplicate: {e}")
                redis_operations.labels(operation='check_duplicate', status='error').inc()
                validation_errors.labels(error_type='redis_error').inc()
                self.rabbitmq_client.nack(method.delivery_tag, requeue=True)
                return

            if is_duplicate:
                # ═══════════════════════════════════════════════════════════════
                # DDoS PROTECTION #3: DUPLICATE VOTE HANDLING
                # ═══════════════════════════════════════════════════════════════
                # Duplicates are DROPPED (not queued) to prevent queue overflow
                # Only increment counter for audit/metrics

                logger.warning(f"Duplicate vote detected: {voter_hash}")

                # Increment duplicate counter in Redis (lightweight, no queue/db)
                try:
                    duplicate_counter_key = f"duplicate_count:{voter_hash}"
                    attempt_count = self.redis_client.client.incr(duplicate_counter_key)
                    redis_operations.labels(operation='incr_duplicate', status='success').inc()
                    duplicate_attempts_total.inc()

                    logger.info(f"Duplicate dropped: {voter_hash} (attempt #{attempt_count})")

                except Exception as e:
                    logger.error(f"Redis error incrementing duplicate count: {e}")
                    redis_operations.labels(operation='incr_duplicate', status='error').inc()
                    validation_errors.labels(error_type='redis_error').inc()
                    # On Redis error, still ACK to avoid requeue loop
                    duplicate_attempts_total.inc()

                votes_processed.labels(status='duplicate').inc()

                # ACK the message (DROP - no queue, no database)
                self.rabbitmq_client.ack(method.delivery_tag)

                # Record latency
                validation_latency.observe(time.time() - start_time)
                return

            # Step 3: Valid and new vote - process it
            logger.info(f"Valid new vote: {voter_hash}")

            # Mark as voted in Redis
            try:
                self.redis_client.mark_as_voted(voter_hash)
                redis_operations.labels(operation='mark_voted', status='success').inc()
            except Exception as e:
                logger.error(f"Redis error marking as voted: {e}")
                redis_operations.labels(operation='mark_voted', status='error').inc()
                validation_errors.labels(error_type='redis_error').inc()
                self.rabbitmq_client.nack(method.delivery_tag, requeue=True)
                return

            # Insert into audit log
            try:
                metadata = {
                    'worker_id': Config.WORKER_ID,
                    'validation_timestamp': datetime.utcnow().isoformat()
                }

                self.db_client.insert_audit_log(
                    voter_hash=voter_hash,
                    law_id=law_id,
                    vote=vote,
                    status='validated',
                    vote_timestamp=vote_timestamp,
                    metadata=metadata
                )
                db_operations.labels(operation='insert_audit', status='success').inc()
            except Exception as e:
                logger.error(f"Database error inserting audit log: {e}")
                db_operations.labels(operation='insert_audit', status='error').inc()
                validation_errors.labels(error_type='database_error').inc()

                # Rollback Redis operation
                try:
                    self.redis_client.client.srem('voted_hashes', voter_hash)
                    logger.info(f"Rolled back Redis operation for {voter_hash}")
                except Exception as rollback_error:
                    logger.error(f"Failed to rollback Redis operation: {rollback_error}")

                self.rabbitmq_client.nack(method.delivery_tag, requeue=True)
                return

            # Publish to aggregation queue
            aggregation_message = {
                'voter_hash': voter_hash,
                'law_id': law_id,
                'vote': vote,
                'vote_timestamp': vote_timestamp_str,
                'status': 'valid',
                'processed_timestamp': datetime.utcnow().isoformat()
            }

            self.rabbitmq_client.publish(Config.AGGREGATION_QUEUE, aggregation_message)
            votes_processed.labels(status='valid').inc()

            # ACK the message
            self.rabbitmq_client.ack(method.delivery_tag)

            logger.info(f"Successfully processed valid vote: {voter_hash}")

            # Record latency
            validation_latency.observe(time.time() - start_time)

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in message: {e}")
            validation_errors.labels(error_type='json_decode').inc()
            self.rabbitmq_client.reject(method.delivery_tag, requeue=False)

        except Exception as e:
            logger.error(f"Unexpected error processing vote: {e}", exc_info=True)
            validation_errors.labels(error_type='unexpected').inc()
            self.rabbitmq_client.nack(method.delivery_tag, requeue=True)

    def update_queue_metrics(self):
        """Update queue size metrics."""
        try:
            size = self.rabbitmq_client.get_queue_size(Config.VALIDATION_QUEUE)
            queue_size.set(size)
        except Exception as e:
            logger.error(f"Error updating queue metrics: {e}")

    def run(self):
        """Run the validation worker."""
        try:
            # Initialize clients
            self.initialize_clients()

            # Start Prometheus metrics server
            logger.info(f"Starting Prometheus metrics server on port {Config.METRICS_PORT}")
            start_http_server(Config.METRICS_PORT)

            # Start consuming messages
            logger.info(f"Starting to consume from queue: {Config.VALIDATION_QUEUE}")
            self.rabbitmq_client.consume(
                queue=Config.VALIDATION_QUEUE,
                callback=self.process_vote
            )

        except KeyboardInterrupt:
            logger.info("Worker interrupted by user")
        except Exception as e:
            logger.error(f"Worker error: {e}", exc_info=True)
            sys.exit(1)
        finally:
            self.cleanup()

    def cleanup(self):
        """Cleanup resources on shutdown."""
        logger.info("Cleaning up resources...")

        if self.rabbitmq_client:
            try:
                self.rabbitmq_client.close()
            except Exception as e:
                logger.error(f"Error closing RabbitMQ client: {e}")

        if self.redis_client:
            try:
                self.redis_client.close()
            except Exception as e:
                logger.error(f"Error closing Redis client: {e}")

        if self.db_client:
            try:
                self.db_client.close()
            except Exception as e:
                logger.error(f"Error closing database client: {e}")

        logger.info("Cleanup complete. Worker shutting down.")


def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("Starting Validation Worker Service")
    logger.info(f"Worker ID: {Config.WORKER_ID}")
    logger.info(f"RabbitMQ: {Config.RABBITMQ_HOST}:{Config.RABBITMQ_PORT}")
    logger.info(f"Redis: {Config.REDIS_HOST}:{Config.REDIS_PORT}")
    logger.info(f"PostgreSQL: {Config.POSTGRES_HOST}:{Config.POSTGRES_PORT}")
    logger.info("=" * 60)

    worker = ValidationWorker()
    worker.run()


if __name__ == '__main__':
    main()
