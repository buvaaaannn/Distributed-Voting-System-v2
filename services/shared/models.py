"""
Shared data models and utilities for the distributed voting system.

This module contains:
- VoteMessage: Data structure for messages passed through RabbitMQ
- Hash generation and validation utilities
- Common data validation functions
"""

import hashlib
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum


class VoteStatus(str, Enum):
    """Status of a vote in the processing pipeline."""
    PENDING = "pending"
    VALIDATED = "validated"
    DUPLICATE = "duplicate"
    INVALID = "invalid"
    AGGREGATED = "aggregated"


class VoteChoice(str, Enum):
    """Valid vote choices."""
    OUI = "oui"
    NON = "non"


@dataclass
class VoteMessage:
    """
    Data structure for vote messages passed through RabbitMQ.

    Attributes:
        nas: National Assurance String (voter identifier)
        code: Verification code
        law_id: Law identifier being voted on
        vote: Vote choice (oui/non)
        hash: SHA-256 hash of NAS+Code
        timestamp: ISO format timestamp when vote was received
        status: Current processing status
        duplicate_count: Number of times this hash has been submitted (for duplicates)
    """
    nas: str
    code: str
    law_id: str
    vote: str
    hash: str
    timestamp: str
    status: str = VoteStatus.PENDING
    duplicate_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string for message queue."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VoteMessage':
        """Create VoteMessage from dictionary."""
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> 'VoteMessage':
        """Create VoteMessage from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    def validate(self) -> tuple[bool, Optional[str]]:
        """
        Validate vote message data.

        Returns:
            tuple: (is_valid, error_message)
        """
        # Validate NAS format (9 digits)
        if not self.nas or not self.nas.isdigit() or len(self.nas) != 9:
            return False, "NAS must be exactly 9 digits"

        # Validate code format (6 alphanumeric characters)
        if not self.code or not self.code.isalnum() or len(self.code) != 6:
            return False, "Code must be exactly 6 alphanumeric characters"

        # Validate law_id format
        if not self.law_id or len(self.law_id) < 1:
            return False, "Law ID is required"

        # Validate vote choice
        if self.vote not in [VoteChoice.OUI, VoteChoice.NON]:
            return False, f"Vote must be '{VoteChoice.OUI}' or '{VoteChoice.NON}'"

        # Validate hash matches
        expected_hash = generate_voter_hash(self.nas, self.code)
        if self.hash != expected_hash:
            return False, "Hash does not match NAS and Code"

        return True, None


def generate_voter_hash(nas: str, code: str) -> str:
    """
    Generate SHA-256 hash from NAS and Code.

    This is the primary identifier for a voter. The hash ensures that:
    1. No PII (NAS) is stored in the system
    2. Each voter can be uniquely identified
    3. Duplicate votes can be detected

    Args:
        nas: National Assurance String (9 digits)
        code: Verification code (6 alphanumeric characters)

    Returns:
        str: Hexadecimal SHA-256 hash
    """
    combined = f"{nas}{code}"
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()


def validate_nas_format(nas: str) -> bool:
    """
    Validate NAS format.

    Args:
        nas: National Assurance String to validate

    Returns:
        bool: True if valid format
    """
    return nas.isdigit() and len(nas) == 9


def validate_code_format(code: str) -> bool:
    """
    Validate verification code format.

    Args:
        code: Verification code to validate

    Returns:
        bool: True if valid format
    """
    return code.isalnum() and len(code) == 6


def validate_law_id_format(law_id: str) -> bool:
    """
    Validate law ID format.

    Args:
        law_id: Law identifier to validate

    Returns:
        bool: True if valid format
    """
    return len(law_id) > 0 and len(law_id) <= 50


def validate_vote_choice(vote: str) -> bool:
    """
    Validate vote choice.

    Args:
        vote: Vote choice to validate

    Returns:
        bool: True if valid choice
    """
    return vote.lower() in [VoteChoice.OUI, VoteChoice.NON]


def create_vote_message(
    nas: str,
    code: str,
    law_id: str,
    vote: str,
    timestamp: Optional[str] = None
) -> VoteMessage:
    """
    Create a VoteMessage with generated hash.

    Args:
        nas: National Assurance String
        code: Verification code
        law_id: Law identifier
        vote: Vote choice (oui/non)
        timestamp: Optional timestamp (defaults to current time)

    Returns:
        VoteMessage: Constructed vote message
    """
    vote_hash = generate_voter_hash(nas, code)

    if timestamp is None:
        timestamp = datetime.utcnow().isoformat() + 'Z'

    return VoteMessage(
        nas=nas,
        code=code,
        law_id=law_id,
        vote=vote.lower(),
        hash=vote_hash,
        timestamp=timestamp,
        status=VoteStatus.PENDING,
        duplicate_count=0
    )


def get_current_timestamp() -> str:
    """
    Get current UTC timestamp in ISO format.

    Returns:
        str: ISO format timestamp with Z suffix
    """
    return datetime.utcnow().isoformat() + 'Z'


# Redis key prefixes for different data types
REDIS_KEYS = {
    'valid_hashes': 'valid_hashes',           # SET of all valid voter hashes
    'voted_hashes': 'voted_hashes',           # SET of hashes that have voted
    'duplicate_count': 'duplicate_count:{}',  # COUNTER for duplicate attempts
    'vote_metadata': 'vote_metadata:{}',      # HASH for vote metadata
}


def get_redis_key(key_type: str, *args) -> str:
    """
    Get formatted Redis key.

    Args:
        key_type: Type of key from REDIS_KEYS
        *args: Arguments to format into key

    Returns:
        str: Formatted Redis key
    """
    key_template = REDIS_KEYS.get(key_type)
    if key_template and '{}' in key_template:
        return key_template.format(*args)
    return key_template


# RabbitMQ exchange and queue names
RABBITMQ_CONFIG = {
    'exchange': 'votes',
    'queues': {
        'validation': 'validation_queue',
        'aggregation': 'aggregation_queue',
        'review': 'review_queue',
    },
    'routing_keys': {
        'validation': 'vote.validation',
        'aggregation': 'vote.aggregation',
        'review': 'vote.review',
    }
}


def get_queue_name(queue_type: str) -> str:
    """
    Get RabbitMQ queue name.

    Args:
        queue_type: Type of queue (validation, aggregation, review)

    Returns:
        str: Queue name
    """
    return RABBITMQ_CONFIG['queues'].get(queue_type, '')


def get_routing_key(queue_type: str) -> str:
    """
    Get RabbitMQ routing key.

    Args:
        queue_type: Type of queue (validation, aggregation, review)

    Returns:
        str: Routing key
    """
    return RABBITMQ_CONFIG['routing_keys'].get(queue_type, '')
