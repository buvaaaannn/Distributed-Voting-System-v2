#!/usr/bin/env python3
"""
Test script to publish sample votes to RabbitMQ for testing the aggregator.
"""
import json
import time
import random
import hashlib
from datetime import datetime
import pika

# Configuration
RABBITMQ_HOST = 'localhost'
RABBITMQ_PORT = 5672
RABBITMQ_USER = 'guest'
RABBITMQ_PASSWORD = 'guest'
RABBITMQ_QUEUE = 'votes.aggregation'

# Sample data
LAW_IDS = ['law-001', 'law-002', 'law-003', 'law-004', 'law-005']
CHOICES = ['oui', 'non']


def generate_vote_hash(citizen_id: str, law_id: str, timestamp: str) -> str:
    """Generate a unique vote hash."""
    data = f"{citizen_id}:{law_id}:{timestamp}"
    return hashlib.sha256(data.encode()).hexdigest()


def create_sample_vote(citizen_id: int) -> dict:
    """Create a sample vote."""
    law_id = random.choice(LAW_IDS)
    choice = random.choice(CHOICES)
    timestamp = datetime.utcnow().isoformat() + 'Z'

    vote = {
        'vote_hash': generate_vote_hash(f'citizen-{citizen_id}', law_id, timestamp),
        'citizen_id': f'citizen-{citizen_id}',
        'law_id': law_id,
        'choice': choice,
        'timestamp': timestamp,
        'metadata': {
            'ip_address': f'192.168.1.{random.randint(1, 255)}',
            'user_agent': 'Mozilla/5.0'
        }
    }
    return vote


def publish_votes(num_votes: int = 1000, batch_size: int = 100):
    """
    Publish sample votes to RabbitMQ.

    Args:
        num_votes: Total number of votes to publish
        batch_size: Number of votes to publish in each batch
    """
    # Connect to RabbitMQ
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
    parameters = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        credentials=credentials
    )

    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()

    # Declare queue
    channel.queue_declare(
        queue=RABBITMQ_QUEUE,
        durable=True,
        arguments={'x-max-priority': 10}
    )

    print(f"Publishing {num_votes} votes to queue '{RABBITMQ_QUEUE}'...")
    print("=" * 60)

    published = 0
    start_time = time.time()

    for i in range(num_votes):
        vote = create_sample_vote(i)

        # Publish message
        channel.basic_publish(
            exchange='',
            routing_key=RABBITMQ_QUEUE,
            body=json.dumps(vote),
            properties=pika.BasicProperties(
                delivery_mode=2,  # Make message persistent
                content_type='application/json'
            )
        )

        published += 1

        # Progress update
        if published % batch_size == 0:
            elapsed = time.time() - start_time
            rate = published / elapsed if elapsed > 0 else 0
            print(f"Published: {published}/{num_votes} votes ({rate:.0f} votes/sec)")

        # Small delay to avoid overwhelming the system
        if i % 100 == 0 and i > 0:
            time.sleep(0.1)

    # Final statistics
    elapsed = time.time() - start_time
    rate = num_votes / elapsed if elapsed > 0 else 0

    print("=" * 60)
    print(f"✓ Published {num_votes} votes successfully!")
    print(f"  Total time: {elapsed:.2f} seconds")
    print(f"  Average rate: {rate:.0f} votes/sec")
    print(f"  Queue: {RABBITMQ_QUEUE}")

    # Close connection
    connection.close()


def show_vote_distribution():
    """Show distribution of votes by law."""
    print("\nVote Distribution:")
    print("-" * 60)

    for law_id in LAW_IDS:
        print(f"  {law_id}: Random votes for 'oui' and 'non'")

    print("-" * 60)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Publish test votes to RabbitMQ')
    parser.add_argument(
        '-n', '--num-votes',
        type=int,
        default=1000,
        help='Number of votes to publish (default: 1000)'
    )
    parser.add_argument(
        '-b', '--batch-size',
        type=int,
        default=100,
        help='Progress update interval (default: 100)'
    )

    args = parser.parse_args()

    show_vote_distribution()

    try:
        publish_votes(args.num_votes, args.batch_size)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
