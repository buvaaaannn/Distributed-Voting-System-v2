"""End-to-end integration tests for the complete vote flow.

Tests the full voting pipeline from API submission through validation,
deduplication, aggregation, and storage in PostgreSQL.

Requires: docker-compose stack running
"""

import hashlib
import time

import httpx
import pytest
import redis


@pytest.mark.docker
@pytest.mark.asyncio
class TestVoteFlow:
    """End-to-end vote flow tests."""

    async def test_submit_valid_vote_and_verify_in_results(
        self,
        api_client: httpx.AsyncClient,
        sample_vote_single: dict,
        load_sample_hashes,
        postgres_client,
        wait_for_processing,
        clear_databases
    ):
        """Test: Submit valid vote and verify it appears in results.

        Flow:
        1. Submit vote via POST /api/v1/vote
        2. Verify 202 Accepted response
        3. Wait for processing (queue -> validation -> aggregation -> DB)
        4. Query results via GET /api/v1/results/{law_id}
        5. Verify vote count incremented correctly
        """
        # Submit vote
        response = await api_client.post(
            "/api/v1/vote",
            json=sample_vote_single
        )

        assert response.status_code == 202
        data = response.json()
        assert "request_id" in data or "status" in data

        # Wait for async processing
        wait_for_processing(3.0)

        # Verify in results
        law_id = sample_vote_single["law_id"]
        results_response = await api_client.get(f"/api/v1/results/{law_id}")

        assert results_response.status_code == 200
        results = results_response.json()

        # Check vote was counted
        vote_choice = sample_vote_single["vote"]
        if vote_choice == "oui":
            assert results.get("oui_count", 0) >= 1
        else:
            assert results.get("non_count", 0) >= 1

        # Verify in audit table
        postgres_client.execute(
            "SELECT COUNT(*) FROM vote_audit WHERE law_id = %s AND status = 'accepted'",
            (law_id,)
        )
        audit_count = postgres_client.fetchone()[0]
        assert audit_count >= 1

    async def test_submit_duplicate_vote_verify_rejection(
        self,
        api_client: httpx.AsyncClient,
        sample_vote_single: dict,
        load_sample_hashes,
        redis_client: redis.Redis,
        postgres_client,
        wait_for_processing,
        generate_hash,
        clear_databases
    ):
        """Test: Submit duplicate vote and verify rejection with counter increment.

        Flow:
        1. Submit vote first time -> accepted
        2. Submit same vote second time -> rejected as duplicate
        3. Verify duplicate counter incremented
        4. Verify only one vote counted in results
        """
        # First submission - should succeed
        response1 = await api_client.post("/api/v1/vote", json=sample_vote_single)
        assert response1.status_code == 202

        wait_for_processing(2.0)

        # Generate hash for verification
        vote_hash = generate_hash(
            sample_vote_single["nas"],
            sample_vote_single["code"],
            sample_vote_single["law_id"]
        )

        # Second submission - should be rejected as duplicate
        response2 = await api_client.post("/api/v1/vote", json=sample_vote_single)

        # Note: API may still return 202 (async processing), but validation will catch it
        # Check Redis duplicate counter
        wait_for_processing(2.0)

        # Verify duplicate tracking in Redis
        duplicate_key = f"duplicate_count:{vote_hash}"
        duplicate_count = redis_client.get(duplicate_key)

        # Should have at least 1 duplicate attempt
        if duplicate_count:
            assert int(duplicate_count) >= 1

        # Verify only one vote counted in results
        law_id = sample_vote_single["law_id"]
        results_response = await api_client.get(f"/api/v1/results/{law_id}")
        assert results_response.status_code == 200
        results = results_response.json()

        vote_choice = sample_vote_single["vote"]
        if vote_choice == "oui":
            assert results.get("oui_count", 0) == 1
        else:
            assert results.get("non_count", 0) == 1

        # Verify duplicate logged in audit table
        postgres_client.execute(
            "SELECT COUNT(*) FROM vote_audit WHERE vote_hash = %s AND status = 'duplicate'",
            (vote_hash,)
        )
        duplicate_audit_count = postgres_client.fetchone()[0]
        assert duplicate_audit_count >= 1

    async def test_submit_invalid_hash_verify_rejection(
        self,
        api_client: httpx.AsyncClient,
        postgres_client,
        wait_for_processing,
        clear_databases
    ):
        """Test: Submit vote with hash not in valid set and verify rejection.

        Flow:
        1. Submit vote with NAS/Code combination NOT in valid_hashes
        2. Verify vote rejected during validation
        3. Verify NOT counted in results
        4. Verify logged as 'invalid' in audit table
        """
        # Create vote with invalid credentials (not in valid_hashes)
        invalid_vote = {
            "nas": "000000000",
            "code": "INVALID",
            "law_id": "L2025-001",
            "vote": "oui"
        }

        # Submit vote (API will accept, but validation will reject)
        response = await api_client.post("/api/v1/vote", json=invalid_vote)

        # API may return 202, but vote will be rejected during validation
        assert response.status_code in [202, 400]

        wait_for_processing(2.0)

        # Verify NOT in results
        results_response = await api_client.get("/api/v1/results/L2025-001")

        if results_response.status_code == 200:
            results = results_response.json()
            # Oui count should be 0 (invalid vote not counted)
            assert results.get("oui_count", 0) == 0

        # Verify logged as invalid in audit table
        vote_hash = hashlib.sha256(
            f"{invalid_vote['nas']}|{invalid_vote['code']}|{invalid_vote['law_id']}".encode()
        ).hexdigest()

        postgres_client.execute(
            "SELECT COUNT(*) FROM vote_audit WHERE vote_hash = %s AND status = 'invalid'",
            (vote_hash,)
        )
        invalid_count = postgres_client.fetchone()[0]
        assert invalid_count >= 1

    async def test_submit_100_votes_verify_all_counted(
        self,
        api_client: httpx.AsyncClient,
        redis_client: redis.Redis,
        postgres_client,
        wait_for_processing,
        generate_hash,
        clear_databases
    ):
        """Test: Submit 100 different votes and verify all counted correctly.

        Flow:
        1. Generate 100 unique votes (50 oui, 50 non)
        2. Add their hashes to valid_hashes
        3. Submit all 100 votes
        4. Verify all 100 counted in results
        5. Verify correct oui/non split
        """
        law_id = "L2025-BULK"
        votes = []
        hashes = []

        # Generate 100 unique votes
        for i in range(100):
            vote = {
                "nas": f"{i:09d}",  # 000000000 to 000000099
                "code": f"CODE{i:04d}",
                "law_id": law_id,
                "vote": "oui" if i < 50 else "non"
            }
            votes.append(vote)

            # Generate and store hash
            vote_hash = generate_hash(vote["nas"], vote["code"], vote["law_id"])
            hashes.append(vote_hash)

        # Add all hashes to valid set
        redis_client.sadd("valid_hashes", *hashes)

        # Submit all votes
        for vote in votes:
            response = await api_client.post("/api/v1/vote", json=vote)
            assert response.status_code in [202, 200]

        # Wait for all to process
        wait_for_processing(5.0)

        # Verify results
        results_response = await api_client.get(f"/api/v1/results/{law_id}")
        assert results_response.status_code == 200
        results = results_response.json()

        # Check counts
        oui_count = results.get("oui_count", 0)
        non_count = results.get("non_count", 0)

        assert oui_count == 50, f"Expected 50 oui votes, got {oui_count}"
        assert non_count == 50, f"Expected 50 non votes, got {non_count}"

        # Verify in audit table
        postgres_client.execute(
            "SELECT COUNT(*) FROM vote_audit WHERE law_id = %s AND status = 'accepted'",
            (law_id,)
        )
        audit_count = postgres_client.fetchone()[0]
        assert audit_count == 100, f"Expected 100 audit entries, got {audit_count}"

        # Cleanup
        redis_client.srem("valid_hashes", *hashes)

    async def test_submit_invalid_format_verify_400_error(
        self,
        api_client: httpx.AsyncClient,
        invalid_votes: list,
        clear_databases
    ):
        """Test: Submit votes with invalid format and verify 400 errors.

        Flow:
        1. Submit votes with various format errors (missing fields, invalid values)
        2. Verify API returns 400 Bad Request or rejects during validation
        3. Verify NOT counted in results
        """
        for invalid_vote in invalid_votes:
            response = await api_client.post("/api/v1/vote", json=invalid_vote)

            # Should return 400 Bad Request or 422 Validation Error
            # (depending on FastAPI validation)
            assert response.status_code in [400, 422], \
                f"Expected 400/422 for invalid vote, got {response.status_code}"

            # Check error response has details
            error_data = response.json()
            assert "detail" in error_data or "error" in error_data

    @pytest.mark.slow
    async def test_concurrent_vote_submission(
        self,
        api_client: httpx.AsyncClient,
        redis_client: redis.Redis,
        wait_for_processing,
        generate_hash,
        clear_databases
    ):
        """Test: Submit multiple votes concurrently and verify no data loss.

        Flow:
        1. Generate 50 unique votes
        2. Submit all concurrently using asyncio
        3. Verify all votes processed
        4. Verify no duplicates or lost votes
        """
        import asyncio

        law_id = "L2025-CONCURRENT"
        vote_count = 50

        # Generate votes and hashes
        votes = []
        hashes = []
        for i in range(vote_count):
            vote = {
                "nas": f"{i:09d}",
                "code": f"ASYNC{i:03d}",
                "law_id": law_id,
                "vote": "oui" if i % 2 == 0 else "non"
            }
            votes.append(vote)
            vote_hash = generate_hash(vote["nas"], vote["code"], vote["law_id"])
            hashes.append(vote_hash)

        # Add to valid hashes
        redis_client.sadd("valid_hashes", *hashes)

        # Submit all concurrently
        tasks = [
            api_client.post("/api/v1/vote", json=vote)
            for vote in votes
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify all submissions accepted
        success_count = sum(
            1 for r in responses
            if not isinstance(r, Exception) and r.status_code in [200, 202]
        )

        assert success_count == vote_count, \
            f"Expected {vote_count} successful submissions, got {success_count}"

        # Wait for processing
        wait_for_processing(5.0)

        # Verify results
        results_response = await api_client.get(f"/api/v1/results/{law_id}")
        assert results_response.status_code == 200
        results = results_response.json()

        total_votes = results.get("oui_count", 0) + results.get("non_count", 0)
        assert total_votes == vote_count, \
            f"Expected {vote_count} total votes, got {total_votes}"

        # Cleanup
        redis_client.srem("valid_hashes", *hashes)

    async def test_vote_flow_with_multiple_laws(
        self,
        api_client: httpx.AsyncClient,
        redis_client: redis.Redis,
        postgres_client,
        wait_for_processing,
        generate_hash,
        clear_databases
    ):
        """Test: Submit votes for multiple different laws and verify isolation.

        Flow:
        1. Submit votes for 3 different law_ids
        2. Verify each law has independent vote counts
        3. Verify no cross-contamination between laws
        """
        laws = ["L2025-001", "L2025-002", "L2025-003"]
        votes_per_law = 10

        all_hashes = []

        for law_id in laws:
            for i in range(votes_per_law):
                vote = {
                    "nas": f"{len(all_hashes):09d}",
                    "code": f"LAW{len(all_hashes):04d}",
                    "law_id": law_id,
                    "vote": "oui" if i < 5 else "non"
                }

                vote_hash = generate_hash(vote["nas"], vote["code"], vote["law_id"])
                all_hashes.append(vote_hash)

                # Add to valid hashes
                redis_client.sadd("valid_hashes", vote_hash)

                # Submit vote
                response = await api_client.post("/api/v1/vote", json=vote)
                assert response.status_code in [200, 202]

        # Wait for processing
        wait_for_processing(5.0)

        # Verify each law independently
        for law_id in laws:
            results_response = await api_client.get(f"/api/v1/results/{law_id}")
            assert results_response.status_code == 200
            results = results_response.json()

            # Each law should have exactly 10 votes (5 oui, 5 non)
            assert results.get("oui_count", 0) == 5
            assert results.get("non_count", 0) == 5

        # Cleanup
        if all_hashes:
            redis_client.srem("valid_hashes", *all_hashes)
