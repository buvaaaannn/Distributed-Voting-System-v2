"""Pytest fixtures for integration tests.

This module provides shared fixtures for integration testing the voting system.
Fixtures handle setup/teardown of docker-compose stack, database connections,
and test data management.
"""

import asyncio
import json
import os
import subprocess
import time
from typing import AsyncGenerator, Dict, Generator, List

import httpx
import psycopg2
import pytest
import redis
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


@pytest.fixture(scope="session")
def docker_compose():
    """Start docker-compose stack for testing, tear down after tests complete.

    This fixture ensures all services (API, RabbitMQ, Redis, PostgreSQL) are
    running before tests begin and properly cleaned up afterward.
    """
    # Path to docker-compose file
    compose_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "docker-compose.yml"
    )

    # Check if docker-compose file exists
    if not os.path.exists(compose_file):
        pytest.skip(f"docker-compose.yml not found at {compose_file}")

    # Start services
    print("\n🚀 Starting docker-compose stack...")
    subprocess.run(
        ["docker-compose", "-f", compose_file, "up", "-d"],
        check=True,
        capture_output=True
    )

    # Wait for services to be ready
    print("⏳ Waiting for services to be healthy...")
    max_attempts = 30
    for i in range(max_attempts):
        try:
            # Check if API is responding
            response = httpx.get("http://localhost:8000/api/v1/health", timeout=2.0)
            if response.status_code == 200:
                print(f"✅ Services ready after {i+1} attempts")
                break
        except (httpx.ConnectError, httpx.ReadTimeout):
            if i == max_attempts - 1:
                pytest.fail("Services did not become healthy in time")
            time.sleep(2)

    yield

    # Teardown: stop and remove containers
    print("\n🛑 Stopping docker-compose stack...")
    subprocess.run(
        ["docker-compose", "-f", compose_file, "down", "-v"],
        check=False,
        capture_output=True
    )


@pytest.fixture(scope="session")
def base_url() -> str:
    """Base URL for the voting API."""
    return os.getenv("API_BASE_URL", "http://localhost:8000")


@pytest.fixture
async def api_client(base_url: str) -> AsyncGenerator[httpx.AsyncClient, None]:
    """HTTP client for making API requests.

    Returns an async httpx client configured for the voting API.
    """
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        yield client


@pytest.fixture(scope="session")
def redis_client() -> Generator[redis.Redis, None, None]:
    """Redis client for direct database operations.

    Yields a connected Redis client for test assertions and setup.
    """
    client = redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        db=int(os.getenv("REDIS_DB", "0")),
        decode_responses=True
    )

    # Test connection
    try:
        client.ping()
    except redis.ConnectionError:
        pytest.skip("Redis not available")

    yield client

    client.close()


@pytest.fixture(scope="session")
def postgres_connection():
    """PostgreSQL connection for direct database operations.

    Yields a psycopg2 connection for test assertions and setup.
    """
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "election_db"),
        user=os.getenv("POSTGRES_USER", "election_user"),
        password=os.getenv("POSTGRES_PASSWORD", "election_pass")
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

    yield conn

    conn.close()


@pytest.fixture
def postgres_client(postgres_connection):
    """PostgreSQL cursor for executing queries.

    Yields a cursor from the session-scoped connection.
    """
    cursor = postgres_connection.cursor()
    yield cursor
    cursor.close()


@pytest.fixture
def clear_databases(redis_client: redis.Redis, postgres_client):
    """Clear all test data from Redis and PostgreSQL.

    Run before each test to ensure clean state.
    """
    # Clear Redis test keys (preserve valid_hashes)
    voted_hashes = redis_client.keys("voted_hashes*")
    duplicate_count = redis_client.keys("duplicate_count:*")

    if voted_hashes:
        redis_client.delete(*voted_hashes)
    if duplicate_count:
        redis_client.delete(*duplicate_count)

    # Clear PostgreSQL tables
    postgres_client.execute("TRUNCATE TABLE vote_audit")
    postgres_client.execute("TRUNCATE TABLE duplicate_attempts")
    postgres_client.execute("DELETE FROM vote_results")

    yield

    # Cleanup after test (optional, but good practice)
    # Same cleanup as above could be repeated here


@pytest.fixture
def sample_votes() -> List[Dict[str, str]]:
    """Sample vote data for testing.

    Returns a list of valid vote payloads with different NAS/Code combinations.
    """
    return [
        {
            "nas": "123456789",
            "code": "ABC123",
            "law_id": "L2025-001",
            "vote": "oui"
        },
        {
            "nas": "987654321",
            "code": "XYZ789",
            "law_id": "L2025-001",
            "vote": "non"
        },
        {
            "nas": "555555555",
            "code": "TEST01",
            "law_id": "L2025-002",
            "vote": "oui"
        },
        {
            "nas": "111111111",
            "code": "DEMO99",
            "law_id": "L2025-001",
            "vote": "oui"
        },
        {
            "nas": "999999999",
            "code": "SAMPLE",
            "law_id": "L2025-002",
            "vote": "non"
        },
    ]


@pytest.fixture
def sample_vote_single() -> Dict[str, str]:
    """Single sample vote for simple tests."""
    return {
        "nas": "123456789",
        "code": "ABC123",
        "law_id": "L2025-001",
        "vote": "oui"
    }


@pytest.fixture
def invalid_votes() -> List[Dict[str, str]]:
    """Invalid vote data for negative testing.

    Returns vote payloads with various validation errors.
    """
    return [
        # Missing fields
        {
            "nas": "123456789",
            "code": "ABC123",
            "vote": "oui"
            # Missing law_id
        },
        # Invalid vote value
        {
            "nas": "123456789",
            "code": "ABC123",
            "law_id": "L2025-001",
            "vote": "maybe"  # Should be 'oui' or 'non'
        },
        # Invalid NAS format
        {
            "nas": "abc",  # Should be 9 digits
            "code": "ABC123",
            "law_id": "L2025-001",
            "vote": "oui"
        },
        # Empty code
        {
            "nas": "123456789",
            "code": "",
            "law_id": "L2025-001",
            "vote": "oui"
        },
        # Extra fields (should still work, but good to test)
        {
            "nas": "123456789",
            "code": "ABC123",
            "law_id": "L2025-001",
            "vote": "oui",
            "extra_field": "should_be_ignored"
        },
    ]


@pytest.fixture
def load_sample_hashes(redis_client: redis.Redis, sample_votes: List[Dict[str, str]]):
    """Load sample vote hashes into Redis valid_hashes set.

    This ensures the sample votes will pass hash validation.
    Generates hashes using the same algorithm as the system.
    """
    import hashlib

    hashes = []
    for vote in sample_votes:
        # Generate hash: sha256(nas|code|law_id)
        hash_input = f"{vote['nas']}|{vote['code']}|{vote['law_id']}"
        vote_hash = hashlib.sha256(hash_input.encode()).hexdigest()
        hashes.append(vote_hash)

    # Add to Redis
    if hashes:
        redis_client.sadd("valid_hashes", *hashes)

    yield hashes

    # Cleanup: remove the added hashes
    if hashes:
        redis_client.srem("valid_hashes", *hashes)


@pytest.fixture
def wait_for_processing():
    """Helper fixture to wait for async vote processing.

    Returns a function that waits for votes to be processed through
    the queue system (RabbitMQ -> Validation -> Aggregation -> DB).
    """
    def _wait(seconds: float = 2.0):
        """Wait for vote processing to complete.

        Args:
            seconds: Time to wait in seconds (default 2.0)
        """
        time.sleep(seconds)

    return _wait


@pytest.fixture
def generate_hash():
    """Helper fixture to generate vote hashes.

    Returns a function that generates SHA256 hash from vote components.
    """
    import hashlib

    def _generate(nas: str, code: str, law_id: str) -> str:
        """Generate vote hash.

        Args:
            nas: National Access Code
            code: Unique voter code
            law_id: Law identifier

        Returns:
            SHA256 hash as hex string
        """
        hash_input = f"{nas}|{code}|{law_id}"
        return hashlib.sha256(hash_input.encode()).hexdigest()

    return _generate


# Event loop configuration for async tests
@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests.

    This ensures pytest-asyncio works properly with session-scoped fixtures.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Marker for tests that require the full docker stack
def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line(
        "markers",
        "docker: mark test as requiring docker-compose stack"
    )
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers",
        "load: mark test as load/performance test"
    )
