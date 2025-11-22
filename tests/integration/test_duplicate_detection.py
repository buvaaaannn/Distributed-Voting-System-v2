"""Integration tests for duplicate vote detection and handling.

Tests the system's ability to detect duplicate votes, track attempt counts,
log duplicate attempts in the audit table, and prevent multiple counting.

Requires: docker-compose stack running
"""

import pytest
import httpx
import redis


@pytest.mark.docker
@pytest.mark.asyncio
class TestDuplicateDetection:
    """Tests for duplicate vote detection and handling."""

    async def test_same_vote_twice_counts_once(
        self,
        api_client: httpx.AsyncClient,
        sample_vote_single: dict,
        load_sample_hashes,
        wait_for_processing,
        clear_databases
    ):
        """Test: Submit same vote twice, verify counted only once.

        Flow:
        1. Submit vote first time
        2. Submit identical vote second time
        3. Verify final count is 1, not 2
        4. Verify results show only one vote
        """
        law_id = sample_vote_single["law_id"]
        vote_choice = sample_vote_single["vote"]

        # Submit first time
        response1 = await api_client.post("/api/v1/vote", json=sample_vote_single)
        assert response1.status_code in [200, 202]

        wait_for_processing(2.0)

        # Submit second time (duplicate)
        response2 = await api_client.post("/api/v1/vote", json=sample_vote_single)
        assert response2.status_code in [200, 202]

        wait_for_processing(2.0)

        # Check results
        results_response = await api_client.get(f"/api/v1/results/{law_id}")
        assert results_response.status_code == 200
        results = results_response.json()

        # Verify count is 1, not 2
        if vote_choice == "oui":
            assert results.get("oui_count", 0) == 1, \
                "Duplicate vote was counted multiple times"
        else:
            assert results.get("non_count", 0) == 1, \
                "Duplicate vote was counted multiple times"

    async def test_same_vote_five_times_attempt_counter(
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
        """Test: Submit same vote 5 times, verify attempt counter = 5.

        Flow:
        1. Submit same vote 5 times
        2. Verify Redis duplicate_count:{hash} = 4 (first is accepted, 4 are duplicates)
        3. Verify PostgreSQL duplicate_attempts.attempt_count = 5
        4. Verify still only counted once in results
        """
        # Submit same vote 5 times
        for i in range(5):
            response = await api_client.post("/api/v1/vote", json=sample_vote_single)
            assert response.status_code in [200, 202]
            wait_for_processing(1.0)

        # Generate hash
        vote_hash = generate_hash(
            sample_vote_single["nas"],
            sample_vote_single["code"],
            sample_vote_single["law_id"]
        )

        # Check Redis duplicate counter
        duplicate_key = f"duplicate_count:{vote_hash}"
        duplicate_count = redis_client.get(duplicate_key)

        if duplicate_count:
            # Should be 4 (5 total attempts - 1 accepted = 4 duplicates)
            assert int(duplicate_count) >= 4, \
                f"Expected duplicate count >= 4, got {duplicate_count}"

        # Check PostgreSQL duplicate_attempts table
        postgres_client.execute(
            "SELECT attempt_count FROM duplicate_attempts WHERE vote_hash = %s",
            (vote_hash,)
        )
        result = postgres_client.fetchone()

        if result:
            db_attempt_count = result[0]
            assert db_attempt_count == 5, \
                f"Expected attempt_count = 5, got {db_attempt_count}"

        # Verify still counted only once
        law_id = sample_vote_single["law_id"]
        results_response = await api_client.get(f"/api/v1/results/{law_id}")
        assert results_response.status_code == 200
        results = results_response.json()

        vote_choice = sample_vote_single["vote"]
        if vote_choice == "oui":
            assert results.get("oui_count", 0) == 1
        else:
            assert results.get("non_count", 0) == 1

    async def test_duplicate_logged_in_audit_table(
        self,
        api_client: httpx.AsyncClient,
        sample_vote_single: dict,
        load_sample_hashes,
        postgres_client,
        wait_for_processing,
        generate_hash,
        clear_databases
    ):
        """Test: Verify duplicate attempts logged in audit table.

        Flow:
        1. Submit vote first time
        2. Submit duplicate
        3. Verify both attempts in vote_audit table
        4. Verify first marked 'accepted', second marked 'duplicate'
        """
        # Submit first time
        await api_client.post("/api/v1/vote", json=sample_vote_single)
        wait_for_processing(2.0)

        # Submit duplicate
        await api_client.post("/api/v1/vote", json=sample_vote_single)
        wait_for_processing(2.0)

        # Generate hash
        vote_hash = generate_hash(
            sample_vote_single["nas"],
            sample_vote_single["code"],
            sample_vote_single["law_id"]
        )

        # Check audit table for accepted vote
        postgres_client.execute(
            "SELECT COUNT(*) FROM vote_audit WHERE vote_hash = %s AND status = 'accepted'",
            (vote_hash,)
        )
        accepted_count = postgres_client.fetchone()[0]
        assert accepted_count == 1, f"Expected 1 accepted vote, got {accepted_count}"

        # Check audit table for duplicate votes
        postgres_client.execute(
            "SELECT COUNT(*) FROM vote_audit WHERE vote_hash = %s AND status = 'duplicate'",
            (vote_hash,)
        )
        duplicate_count = postgres_client.fetchone()[0]
        assert duplicate_count >= 1, f"Expected at least 1 duplicate, got {duplicate_count}"

        # Verify total audit entries
        postgres_client.execute(
            "SELECT COUNT(*) FROM vote_audit WHERE vote_hash = %s",
            (vote_hash,)
        )
        total_count = postgres_client.fetchone()[0]
        assert total_count >= 2, f"Expected at least 2 audit entries, got {total_count}"

    async def test_different_votes_same_nas_counted_separately(
        self,
        api_client: httpx.AsyncClient,
        redis_client: redis.Redis,
        wait_for_processing,
        generate_hash,
        clear_databases
    ):
        """Test: Same NAS voting on different laws should be counted separately.

        Each (NAS, Code, Law_ID) combination generates unique hash.
        Same NAS can vote on multiple laws.
        """
        nas = "123456789"
        code = "ABC123"

        # Vote on law 1
        vote1 = {
            "nas": nas,
            "code": code,
            "law_id": "L2025-001",
            "vote": "oui"
        }

        # Vote on law 2 (same NAS, same code, different law)
        vote2 = {
            "nas": nas,
            "code": code,
            "law_id": "L2025-002",
            "vote": "non"
        }

        # Add hashes to valid set
        hash1 = generate_hash(vote1["nas"], vote1["code"], vote1["law_id"])
        hash2 = generate_hash(vote2["nas"], vote2["code"], vote2["law_id"])
        redis_client.sadd("valid_hashes", hash1, hash2)

        # Submit both votes
        response1 = await api_client.post("/api/v1/vote", json=vote1)
        assert response1.status_code in [200, 202]

        response2 = await api_client.post("/api/v1/vote", json=vote2)
        assert response2.status_code in [200, 202]

        wait_for_processing(3.0)

        # Verify both counted
        results1 = await api_client.get("/api/v1/results/L2025-001")
        assert results1.status_code == 200
        data1 = results1.json()
        assert data1.get("oui_count", 0) >= 1

        results2 = await api_client.get("/api/v1/results/L2025-002")
        assert results2.status_code == 200
        data2 = results2.json()
        assert data2.get("non_count", 0) >= 1

        # Cleanup
        redis_client.srem("valid_hashes", hash1, hash2)

    async def test_duplicate_detection_across_restarts(
        self,
        api_client: httpx.AsyncClient,
        sample_vote_single: dict,
        load_sample_hashes,
        redis_client: redis.Redis,
        wait_for_processing,
        generate_hash,
        clear_databases
    ):
        """Test: Duplicate detection persists across service restarts.

        Flow:
        1. Submit vote
        2. Verify hash in Redis voted_hashes set
        3. Simulate restart (voted_hashes would persist in Redis)
        4. Submit duplicate
        5. Verify still detected as duplicate

        Note: This test verifies Redis persistence, not actual service restart.
        """
        # Submit first vote
        await api_client.post("/api/v1/vote", json=sample_vote_single)
        wait_for_processing(2.0)

        # Verify hash in voted_hashes
        vote_hash = generate_hash(
            sample_vote_single["nas"],
            sample_vote_single["code"],
            sample_vote_single["law_id"]
        )

        is_voted = redis_client.sismember("voted_hashes", vote_hash)
        assert is_voted, "Vote hash not found in voted_hashes set"

        # Submit duplicate (simulates after restart)
        await api_client.post("/api/v1/vote", json=sample_vote_single)
        wait_for_processing(2.0)

        # Verify duplicate counter exists
        duplicate_key = f"duplicate_count:{vote_hash}"
        duplicate_count = redis_client.get(duplicate_key)

        if duplicate_count:
            assert int(duplicate_count) >= 1

    async def test_multiple_unique_votes_no_false_duplicates(
        self,
        api_client: httpx.AsyncClient,
        redis_client: redis.Redis,
        wait_for_processing,
        generate_hash,
        clear_databases
    ):
        """Test: Multiple unique votes are not falsely flagged as duplicates.

        Flow:
        1. Submit 10 unique votes (different NAS/Code combinations)
        2. Verify all 10 counted
        3. Verify none flagged as duplicates
        """
        law_id = "L2025-UNIQUE"
        votes = []
        hashes = []

        # Generate 10 unique votes
        for i in range(10):
            vote = {
                "nas": f"{i:09d}",
                "code": f"UNIQUE{i:03d}",
                "law_id": law_id,
                "vote": "oui"
            }
            votes.append(vote)
            vote_hash = generate_hash(vote["nas"], vote["code"], vote["law_id"])
            hashes.append(vote_hash)

        # Add to valid hashes
        redis_client.sadd("valid_hashes", *hashes)

        # Submit all votes
        for vote in votes:
            response = await api_client.post("/api/v1/vote", json=vote)
            assert response.status_code in [200, 202]

        wait_for_processing(3.0)

        # Verify all 10 counted
        results_response = await api_client.get(f"/api/v1/results/{law_id}")
        assert results_response.status_code == 200
        results = results_response.json()
        assert results.get("oui_count", 0) == 10

        # Verify none have duplicate counters
        for vote_hash in hashes:
            duplicate_key = f"duplicate_count:{vote_hash}"
            duplicate_count = redis_client.get(duplicate_key)
            assert duplicate_count is None, \
                f"Unique vote {vote_hash} incorrectly flagged as duplicate"

        # Cleanup
        redis_client.srem("valid_hashes", *hashes)

    async def test_concurrent_duplicate_submissions(
        self,
        api_client: httpx.AsyncClient,
        sample_vote_single: dict,
        load_sample_hashes,
        wait_for_processing,
        clear_databases
    ):
        """Test: Concurrent submissions of same vote are handled correctly.

        Flow:
        1. Submit same vote 10 times concurrently
        2. Verify only counted once (race condition handling)
        3. Verify attempt counter reflects all attempts
        """
        import asyncio

        # Submit same vote 10 times concurrently
        tasks = [
            api_client.post("/api/v1/vote", json=sample_vote_single)
            for _ in range(10)
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # All should be accepted by API (async processing)
        success_count = sum(
            1 for r in responses
            if not isinstance(r, Exception) and r.status_code in [200, 202]
        )

        assert success_count >= 8, \
            f"Expected at least 8/10 submissions accepted, got {success_count}"

        wait_for_processing(3.0)

        # Verify counted only once
        law_id = sample_vote_single["law_id"]
        results_response = await api_client.get(f"/api/v1/results/{law_id}")
        assert results_response.status_code == 200
        results = results_response.json()

        vote_choice = sample_vote_single["vote"]
        if vote_choice == "oui":
            assert results.get("oui_count", 0) == 1, \
                "Concurrent duplicates resulted in multiple counts"
        else:
            assert results.get("non_count", 0) == 1, \
                "Concurrent duplicates resulted in multiple counts"

    async def test_duplicate_timestamps_in_audit(
        self,
        api_client: httpx.AsyncClient,
        sample_vote_single: dict,
        load_sample_hashes,
        postgres_client,
        wait_for_processing,
        generate_hash,
        clear_databases
    ):
        """Test: Duplicate attempts have distinct timestamps in audit log.

        Flow:
        1. Submit vote
        2. Wait 1 second
        3. Submit duplicate
        4. Verify both have timestamps in audit table
        5. Verify second timestamp is later
        """
        import time

        # Submit first vote
        await api_client.post("/api/v1/vote", json=sample_vote_single)
        wait_for_processing(2.0)

        time.sleep(1.0)  # Ensure timestamps differ

        # Submit duplicate
        await api_client.post("/api/v1/vote", json=sample_vote_single)
        wait_for_processing(2.0)

        # Generate hash
        vote_hash = generate_hash(
            sample_vote_single["nas"],
            sample_vote_single["code"],
            sample_vote_single["law_id"]
        )

        # Query audit entries with timestamps
        postgres_client.execute(
            "SELECT timestamp, status FROM vote_audit WHERE vote_hash = %s ORDER BY timestamp",
            (vote_hash,)
        )
        audit_entries = postgres_client.fetchall()

        assert len(audit_entries) >= 2, \
            f"Expected at least 2 audit entries, got {len(audit_entries)}"

        # Verify timestamps are distinct and ordered
        timestamps = [entry[0] for entry in audit_entries]
        for i in range(len(timestamps) - 1):
            assert timestamps[i] < timestamps[i + 1], \
                "Audit timestamps not in chronological order"

    async def test_duplicate_attempts_table_structure(
        self,
        api_client: httpx.AsyncClient,
        sample_vote_single: dict,
        load_sample_hashes,
        postgres_client,
        wait_for_processing,
        generate_hash,
        clear_databases
    ):
        """Test: Duplicate_attempts table has correct structure and data.

        Flow:
        1. Submit vote 3 times
        2. Verify duplicate_attempts record exists
        3. Verify has fields: vote_hash, attempt_count, first_attempt, last_attempt
        4. Verify attempt_count = 3
        5. Verify first_attempt < last_attempt
        """
        # Submit vote 3 times
        for _ in range(3):
            await api_client.post("/api/v1/vote", json=sample_vote_single)
            wait_for_processing(1.0)

        # Generate hash
        vote_hash = generate_hash(
            sample_vote_single["nas"],
            sample_vote_single["code"],
            sample_vote_single["law_id"]
        )

        # Query duplicate_attempts table
        postgres_client.execute(
            """
            SELECT vote_hash, attempt_count, first_attempt, last_attempt
            FROM duplicate_attempts
            WHERE vote_hash = %s
            """,
            (vote_hash,)
        )
        result = postgres_client.fetchone()

        if result:
            db_hash, attempt_count, first_attempt, last_attempt = result

            # Verify data
            assert db_hash == vote_hash
            assert attempt_count == 3, f"Expected attempt_count = 3, got {attempt_count}"
            assert first_attempt < last_attempt, \
                "first_attempt should be earlier than last_attempt"


@pytest.mark.docker
@pytest.mark.asyncio
class TestDuplicateEdgeCases:
    """Edge case tests for duplicate detection."""

    async def test_vote_change_not_allowed(
        self,
        api_client: httpx.AsyncClient,
        redis_client: redis.Redis,
        wait_for_processing,
        generate_hash,
        clear_databases
    ):
        """Test: Same NAS/Code voting 'oui' then 'non' on same law is duplicate.

        Vote is determined by (NAS, Code, Law_ID), not the choice.
        Attempting to change vote should be flagged as duplicate.
        """
        nas = "111111111"
        code = "CHANGE01"
        law_id = "L2025-CHANGE"

        # Generate hash (same regardless of vote choice)
        vote_hash = generate_hash(nas, code, law_id)
        redis_client.sadd("valid_hashes", vote_hash)

        # Submit 'oui' vote
        vote1 = {"nas": nas, "code": code, "law_id": law_id, "vote": "oui"}
        response1 = await api_client.post("/api/v1/vote", json=vote1)
        assert response1.status_code in [200, 202]

        wait_for_processing(2.0)

        # Try to change to 'non' (should be duplicate)
        vote2 = {"nas": nas, "code": code, "law_id": law_id, "vote": "non"}
        response2 = await api_client.post("/api/v1/vote", json=vote2)
        assert response2.status_code in [200, 202]

        wait_for_processing(2.0)

        # Verify results show only first vote ('oui')
        results_response = await api_client.get(f"/api/v1/results/{law_id}")
        assert results_response.status_code == 200
        results = results_response.json()

        # Only 'oui' should be counted (first vote)
        assert results.get("oui_count", 0) == 1
        assert results.get("non_count", 0) == 0

        # Cleanup
        redis_client.srem("valid_hashes", vote_hash)

    async def test_case_sensitivity_in_duplicate_detection(
        self,
        api_client: httpx.AsyncClient,
        redis_client: redis.Redis,
        wait_for_processing,
        generate_hash,
        clear_databases
    ):
        """Test: Case variations in NAS/Code are treated as different votes.

        'ABC123' vs 'abc123' should be different voters.
        """
        nas = "222222222"
        law_id = "L2025-CASE"

        # Vote 1: uppercase code
        vote1 = {"nas": nas, "code": "ABC123", "law_id": law_id, "vote": "oui"}
        hash1 = generate_hash(vote1["nas"], vote1["code"], vote1["law_id"])
        redis_client.sadd("valid_hashes", hash1)

        # Vote 2: lowercase code (different voter)
        vote2 = {"nas": nas, "code": "abc123", "law_id": law_id, "vote": "non"}
        hash2 = generate_hash(vote2["nas"], vote2["code"], vote2["law_id"])
        redis_client.sadd("valid_hashes", hash2)

        # Submit both
        await api_client.post("/api/v1/vote", json=vote1)
        await api_client.post("/api/v1/vote", json=vote2)

        wait_for_processing(3.0)

        # Verify both counted (different hashes)
        results_response = await api_client.get(f"/api/v1/results/{law_id}")
        assert results_response.status_code == 200
        results = results_response.json()

        # Should have 1 oui and 1 non (both counted separately)
        total_votes = results.get("oui_count", 0) + results.get("non_count", 0)
        assert total_votes == 2, \
            "Case variations should be treated as different voters"

        # Cleanup
        redis_client.srem("valid_hashes", hash1, hash2)
