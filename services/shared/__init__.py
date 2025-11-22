"""
Shared utilities and models for the distributed voting system.

This package contains common code used across all services:
- Data models (VoteMessage, enums)
- Hash generation utilities
- Validation functions
- Redis and RabbitMQ configuration constants
"""

from .models import (
    VoteMessage,
    VoteStatus,
    VoteChoice,
    generate_voter_hash,
    validate_nas_format,
    validate_code_format,
    validate_law_id_format,
    validate_vote_choice,
    create_vote_message,
    get_current_timestamp,
    get_redis_key,
    get_queue_name,
    get_routing_key,
    REDIS_KEYS,
    RABBITMQ_CONFIG,
)

__all__ = [
    'VoteMessage',
    'VoteStatus',
    'VoteChoice',
    'generate_voter_hash',
    'validate_nas_format',
    'validate_code_format',
    'validate_law_id_format',
    'validate_vote_choice',
    'create_vote_message',
    'get_current_timestamp',
    'get_redis_key',
    'get_queue_name',
    'get_routing_key',
    'REDIS_KEYS',
    'RABBITMQ_CONFIG',
]

__version__ = '2.0.0'
