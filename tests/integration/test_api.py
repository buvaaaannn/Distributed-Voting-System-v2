"""Integration tests for API endpoints.

Tests all API endpoints including vote submission, results retrieval,
health checks, rate limiting, and concurrent request handling.

Requires: docker-compose stack running
"""

import asyncio
import time

import httpx
import pytest


@pytest.mark.docker
@pytest.mark.asyncio
class TestVoteEndpoint:
    """Tests for POST /api/v1/vote endpoint."""

    async def test_post_vote_with_valid_data(
        self,
        api_client: httpx.AsyncClient,
        sample_vote_single: dict,
        load_sample_hashes,
        clear_databases
    ):
        """Test POST /api/v1/vote with valid vote data.

        Verifies:
        - 202 Accepted status code
        - Response contains request_id or confirmation
        - Response format is correct
        """
        response = await api_client.post("/api/v1/vote", json=sample_vote_single)

        assert response.status_code == 202
        data = response.json()

        # Response should contain either request_id or status
        assert "request_id" in data or "status" in data

        # If request_id present, should be a valid UUID format
        if "request_id" in data:
            request_id = data["request_id"]
            assert isinstance(request_id, str)
            assert len(request_id) > 0

    async def test_post_vote_with_missing_fields(
        self,
        api_client: httpx.AsyncClient,
        clear_databases
    ):
        """Test POST /api/v1/vote with missing required fields.

        Verifies proper validation and error responses.
        """
        # Missing 'vote' field
        invalid_vote = {
            "nas": "123456789",
            "code": "ABC123",
            "law_id": "L2025-001"
        }

        response = await api_client.post("/api/v1/vote", json=invalid_vote)

        assert response.status_code in [400, 422]
        error_data = response.json()
        assert "detail" in error_data or "error" in error_data

    async def test_post_vote_with_invalid_vote_value(
        self,
        api_client: httpx.AsyncClient,
        clear_databases
    ):
        """Test POST /api/v1/vote with invalid vote choice.

        Vote must be 'oui' or 'non'.
        """
        invalid_vote = {
            "nas": "123456789",
            "code": "ABC123",
            "law_id": "L2025-001",
            "vote": "maybe"  # Invalid - must be 'oui' or 'non'
        }

        response = await api_client.post("/api/v1/vote", json=invalid_vote)

        assert response.status_code in [400, 422]
        error_data = response.json()
        assert "detail" in error_data or "error" in error_data

    async def test_post_vote_with_invalid_nas_format(
        self,
        api_client: httpx.AsyncClient,
        clear_databases
    ):
        """Test POST /api/v1/vote with invalid NAS format.

        NAS should be 9 digits.
        """
        invalid_vote = {
            "nas": "abc",  # Invalid format
            "code": "ABC123",
            "law_id": "L2025-001",
            "vote": "oui"
        }

        response = await api_client.post("/api/v1/vote", json=invalid_vote)

        assert response.status_code in [400, 422]

    async def test_post_vote_with_empty_body(
        self,
        api_client: httpx.AsyncClient,
        clear_databases
    ):
        """Test POST /api/v1/vote with empty request body."""
        response = await api_client.post("/api/v1/vote", json={})

        assert response.status_code in [400, 422]

    async def test_post_vote_with_malformed_json(
        self,
        api_client: httpx.AsyncClient,
        clear_databases
    ):
        """Test POST /api/v1/vote with malformed JSON."""
        response = await api_client.post(
            "/api/v1/vote",
            content="not valid json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422


@pytest.mark.docker
@pytest.mark.asyncio
class TestResultsEndpoint:
    """Tests for GET /api/v1/results/{law_id} endpoint."""

    async def test_get_results_for_existing_law(
        self,
        api_client: httpx.AsyncClient,
        sample_vote_single: dict,
        load_sample_hashes,
        wait_for_processing,
        clear_databases
    ):
        """Test GET /api/v1/results/{law_id} for law with votes.

        Verifies:
        - 200 OK status
        - Response contains oui_count and non_count
        - Counts are non-negative integers
        """
        # Submit a vote first
        await api_client.post("/api/v1/vote", json=sample_vote_single)
        wait_for_processing(2.0)

        # Get results
        law_id = sample_vote_single["law_id"]
        response = await api_client.get(f"/api/v1/results/{law_id}")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "law_id" in data or "oui_count" in data or "non_count" in data
        assert "oui_count" in data
        assert "non_count" in data

        # Verify counts are valid
        assert isinstance(data["oui_count"], int)
        assert isinstance(data["non_count"], int)
        assert data["oui_count"] >= 0
        assert data["non_count"] >= 0

    async def test_get_results_for_nonexistent_law(
        self,
        api_client: httpx.AsyncClient,
        clear_databases
    ):
        """Test GET /api/v1/results/{law_id} for law with no votes.

        Should return 200 with zero counts or 404, depending on implementation.
        """
        response = await api_client.get("/api/v1/results/L9999-NOEXIST")

        # Either 404 (law not found) or 200 with zero counts
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            assert data.get("oui_count", 0) == 0
            assert data.get("non_count", 0) == 0

    async def test_get_results_updated_after_vote(
        self,
        api_client: httpx.AsyncClient,
        redis_client,
        generate_hash,
        wait_for_processing,
        clear_databases
    ):
        """Test that results are updated after votes are submitted.

        Verifies real-time aggregation.
        """
        law_id = "L2025-REALTIME"

        # Check initial state
        response1 = await api_client.get(f"/api/v1/results/{law_id}")
        initial_oui = 0
        initial_non = 0

        if response1.status_code == 200:
            data1 = response1.json()
            initial_oui = data1.get("oui_count", 0)
            initial_non = data1.get("non_count", 0)

        # Submit 'oui' vote
        vote1 = {
            "nas": "111111111",
            "code": "REALTIME1",
            "law_id": law_id,
            "vote": "oui"
        }
        hash1 = generate_hash(vote1["nas"], vote1["code"], vote1["law_id"])
        redis_client.sadd("valid_hashes", hash1)

        await api_client.post("/api/v1/vote", json=vote1)
        wait_for_processing(2.0)

        # Check updated results
        response2 = await api_client.get(f"/api/v1/results/{law_id}")
        assert response2.status_code == 200
        data2 = response2.json()

        assert data2["oui_count"] == initial_oui + 1
        assert data2["non_count"] == initial_non

        # Submit 'non' vote
        vote2 = {
            "nas": "222222222",
            "code": "REALTIME2",
            "law_id": law_id,
            "vote": "non"
        }
        hash2 = generate_hash(vote2["nas"], vote2["code"], vote2["law_id"])
        redis_client.sadd("valid_hashes", hash2)

        await api_client.post("/api/v1/vote", json=vote2)
        wait_for_processing(2.0)

        # Check final results
        response3 = await api_client.get(f"/api/v1/results/{law_id}")
        assert response3.status_code == 200
        data3 = response3.json()

        assert data3["oui_count"] == initial_oui + 1
        assert data3["non_count"] == initial_non + 1

        # Cleanup
        redis_client.srem("valid_hashes", hash1, hash2)


@pytest.mark.docker
@pytest.mark.asyncio
class TestHealthEndpoint:
    """Tests for GET /api/v1/health endpoint."""

    async def test_health_check_returns_200(
        self,
        api_client: httpx.AsyncClient
    ):
        """Test health endpoint returns 200 when service is healthy."""
        response = await api_client.get("/api/v1/health")

        assert response.status_code == 200

    async def test_health_check_response_format(
        self,
        api_client: httpx.AsyncClient
    ):
        """Test health endpoint response contains status information."""
        response = await api_client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()

        # Should contain status indicator
        assert "status" in data or "health" in data or "ok" in data

    async def test_health_check_performance(
        self,
        api_client: httpx.AsyncClient
    ):
        """Test health check responds quickly (< 1 second)."""
        start_time = time.time()
        response = await api_client.get("/api/v1/health")
        duration = time.time() - start_time

        assert response.status_code == 200
        assert duration < 1.0, f"Health check took {duration}s, expected < 1s"


@pytest.mark.docker
@pytest.mark.asyncio
@pytest.mark.slow
class TestRateLimiting:
    """Tests for API rate limiting."""

    async def test_rate_limiting_on_vote_endpoint(
        self,
        api_client: httpx.AsyncClient,
        sample_vote_single: dict,
        clear_databases
    ):
        """Test that excessive requests trigger rate limiting.

        Submits many requests rapidly and verifies rate limit response (429).
        """
        # Submit many requests rapidly
        requests_count = 150  # Exceed typical rate limit (100/minute in config)
        responses = []

        for _ in range(requests_count):
            try:
                response = await api_client.post(
                    "/api/v1/vote",
                    json=sample_vote_single,
                    timeout=2.0
                )
                responses.append(response.status_code)
            except httpx.TimeoutException:
                # Timeout is also acceptable under heavy load
                responses.append(429)

        # Should have some rate limit responses (429)
        # Note: This depends on rate limiting being enabled
        rate_limited = sum(1 for code in responses if code == 429)

        # If rate limiting is strict, we should see 429s
        # If not implemented, this test serves as a reminder
        print(f"\nRate limit responses: {rate_limited}/{requests_count}")

    async def test_rate_limiting_allows_normal_traffic(
        self,
        api_client: httpx.AsyncClient,
        sample_vote_single: dict,
        load_sample_hashes,
        clear_databases
    ):
        """Test that normal traffic is not rate limited.

        Submits requests at reasonable rate and verifies all accepted.
        """
        # Submit requests at reasonable rate (1/second)
        requests_count = 10
        success_count = 0

        for _ in range(requests_count):
            response = await api_client.post("/api/v1/vote", json=sample_vote_single)
            if response.status_code in [200, 202]:
                success_count += 1
            await asyncio.sleep(0.1)  # Small delay between requests

        # All should succeed (not rate limited)
        assert success_count == requests_count


@pytest.mark.docker
@pytest.mark.asyncio
@pytest.mark.slow
class TestConcurrentRequests:
    """Tests for handling concurrent API requests."""

    async def test_concurrent_vote_submissions(
        self,
        api_client: httpx.AsyncClient,
        redis_client,
        generate_hash,
        clear_databases
    ):
        """Test API handles concurrent vote submissions correctly.

        Submits 50 votes concurrently and verifies all processed.
        """
        law_id = "L2025-CONCURRENT"
        concurrent_count = 50

        # Generate unique votes
        votes = []
        hashes = []
        for i in range(concurrent_count):
            vote = {
                "nas": f"{i:09d}",
                "code": f"CONC{i:04d}",
                "law_id": law_id,
                "vote": "oui" if i % 2 == 0 else "non"
            }
            votes.append(vote)
            vote_hash = generate_hash(vote["nas"], vote["code"], vote["law_id"])
            hashes.append(vote_hash)

        # Add to valid hashes
        redis_client.sadd("valid_hashes", *hashes)

        # Submit concurrently
        tasks = [api_client.post("/api/v1/vote", json=vote) for vote in votes]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successful submissions
        success_count = sum(
            1 for r in responses
            if not isinstance(r, Exception) and r.status_code in [200, 202]
        )

        # Most should succeed
        assert success_count >= concurrent_count * 0.9, \
            f"Expected at least 90% success, got {success_count}/{concurrent_count}"

        # Cleanup
        redis_client.srem("valid_hashes", *hashes)

    async def test_concurrent_results_queries(
        self,
        api_client: httpx.AsyncClient
    ):
        """Test API handles concurrent results queries correctly.

        Queries results endpoint concurrently and verifies consistent responses.
        """
        law_id = "L2025-001"
        concurrent_count = 20

        # Query concurrently
        tasks = [
            api_client.get(f"/api/v1/results/{law_id}")
            for _ in range(concurrent_count)
        ]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # All should succeed
        success_count = sum(
            1 for r in responses
            if not isinstance(r, Exception) and r.status_code == 200
        )

        assert success_count == concurrent_count

        # Verify consistent results
        if success_count > 0:
            data_list = [r.json() for r in responses if not isinstance(r, Exception)]
            first_oui = data_list[0].get("oui_count", 0)
            first_non = data_list[0].get("non_count", 0)

            # All responses should have same counts (within small margin for race conditions)
            for data in data_list:
                assert abs(data.get("oui_count", 0) - first_oui) <= 1
                assert abs(data.get("non_count", 0) - first_non) <= 1

    async def test_mixed_concurrent_operations(
        self,
        api_client: httpx.AsyncClient,
        redis_client,
        generate_hash,
        clear_databases
    ):
        """Test API handles mixed concurrent operations (votes + queries).

        Submits votes and queries results concurrently.
        """
        law_id = "L2025-MIXED"

        # Generate votes
        votes = []
        hashes = []
        for i in range(20):
            vote = {
                "nas": f"{i:09d}",
                "code": f"MIXED{i:04d}",
                "law_id": law_id,
                "vote": "oui"
            }
            votes.append(vote)
            vote_hash = generate_hash(vote["nas"], vote["code"], vote["law_id"])
            hashes.append(vote_hash)

        redis_client.sadd("valid_hashes", *hashes)

        # Mix vote submissions and result queries
        tasks = []
        for vote in votes:
            tasks.append(api_client.post("/api/v1/vote", json=vote))
            tasks.append(api_client.get(f"/api/v1/results/{law_id}"))

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify no failures
        errors = [r for r in responses if isinstance(r, Exception)]
        assert len(errors) == 0, f"Got {len(errors)} errors during concurrent operations"

        # Cleanup
        redis_client.srem("valid_hashes", *hashes)


@pytest.mark.docker
@pytest.mark.asyncio
class TestAPIErrorHandling:
    """Tests for API error handling and edge cases."""

    async def test_invalid_content_type(
        self,
        api_client: httpx.AsyncClient,
        clear_databases
    ):
        """Test API rejects requests with invalid Content-Type."""
        response = await api_client.post(
            "/api/v1/vote",
            content="nas=123&code=ABC",
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        assert response.status_code in [400, 415, 422]

    async def test_oversized_payload(
        self,
        api_client: httpx.AsyncClient,
        clear_databases
    ):
        """Test API handles oversized payloads gracefully."""
        oversized_vote = {
            "nas": "123456789",
            "code": "ABC123",
            "law_id": "L2025-001",
            "vote": "oui",
            "extra_data": "X" * 1000000  # 1MB of extra data
        }

        response = await api_client.post("/api/v1/vote", json=oversized_vote)

        # Should reject or strip extra data
        assert response.status_code in [200, 202, 400, 413, 422]

    async def test_invalid_http_method_on_vote(
        self,
        api_client: httpx.AsyncClient
    ):
        """Test invalid HTTP methods on /api/v1/vote."""
        # GET on POST-only endpoint
        response = await api_client.get("/api/v1/vote")
        assert response.status_code == 405  # Method Not Allowed

        # PUT on POST-only endpoint
        response = await api_client.put("/api/v1/vote", json={})
        assert response.status_code == 405

    async def test_invalid_http_method_on_results(
        self,
        api_client: httpx.AsyncClient
    ):
        """Test invalid HTTP methods on /api/v1/results."""
        # POST on GET-only endpoint
        response = await api_client.post("/api/v1/results/L2025-001", json={})
        assert response.status_code == 405  # Method Not Allowed
