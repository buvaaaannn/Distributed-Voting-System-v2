#!/usr/bin/env python3
"""
Load test for law voting - 250k votes for 'thisisworking' law
"""
import asyncio
import httpx
import time
from datetime import datetime

# Configuration
API_URL = "http://localhost:8000"
LAW_ID = "thisisworking"
NUM_VOTES = 250000

async def submit_vote_async(client: httpx.AsyncClient, vote_data: dict):
    """Submit a single vote."""
    try:
        response = await client.post(f"{API_URL}/api/v1/vote", json=vote_data, timeout=10.0)
        return response.status_code in [200, 202]
    except Exception:
        return False

async def generate_load():
    """Generate load by submitting votes."""
    print("=" * 70)
    print(f"LAW VOTE LOAD TEST - {NUM_VOTES:,} VOTES FOR '{LAW_ID}'")
    print("=" * 70)

    # Load test votes
    try:
        with open('test_votes.txt', 'r') as f:
            lines = f.readlines()[:NUM_VOTES]
    except FileNotFoundError:
        print("ERROR: test_votes.txt not found!")
        return

    print(f"\nLoaded {len(lines):,} pre-generated votes")
    print(f"Target law: {LAW_ID}")
    print("\nStarting load test...\n")

    start_time = time.time()
    success_count = 0
    error_count = 0

    async with httpx.AsyncClient() as client:
        # Process in batches of 1000
        batch_size = 1000
        for i in range(0, len(lines), batch_size):
            batch = lines[i:i+batch_size]
            tasks = []

            for line in batch:
                nas, code, _, _ = line.strip().split('|')
                vote = random.choice(['oui', 'non'])

                vote_data = {
                    "nas": nas,
                    "code": code,
                    "law_id": LAW_ID,
                    "vote": vote
                }
                tasks.append(submit_vote_async(client, vote_data))

            # Submit batch
            results = await asyncio.gather(*tasks)
            success_count += sum(results)
            error_count += len(results) - sum(results)

            # Progress update
            if (i + batch_size) % 10000 == 0:
                elapsed = time.time() - start_time
                rate = (i + batch_size) / elapsed
                print(f"   LAW: {i + batch_size:,}/{len(lines):,} votes ({rate:.0f} votes/sec)")

    duration = time.time() - start_time
    rate = len(lines) / duration

    print(f"\n{'=' * 70}")
    print(f"LAW VOTE TEST COMPLETE")
    print(f"{'=' * 70}")
    print(f"Duration: {duration:.2f}s")
    print(f"Total: {len(lines):,} votes")
    print(f"Success: {success_count:,}")
    print(f"Errors: {error_count:,}")
    print(f"Rate: {rate:.0f} votes/sec")
    print(f"{'=' * 70}\n")

import random

if __name__ == "__main__":
    asyncio.run(generate_load())
