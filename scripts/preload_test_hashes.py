#!/usr/bin/env python3
"""
Pre-load valid vote hashes into Redis for load testing.
This ensures load test votes will be validated successfully.

Author: David Marleau
Project: Distributed Voting System - Demo Version
"""
import redis
import hashlib
import sys
import time
from typing import List, Tuple

def generate_vote_data(count: int) -> List[Tuple[str, str, str, str]]:
    """Generate test vote data (nas, code, law_id, vote)."""
    votes = []
    laws = ['L2025-001', 'L2025-002', 'L2025-003']
    choices = ['oui', 'non']

    print(f"Generating {count} vote credentials...")
    for i in range(count):
        nas = f"{i:09d}"  # 9-digit NAS
        code = f"T{i:05d}"  # 6-char code
        law_id = laws[i % len(laws)]  # Distribute across laws
        vote = choices[i % len(choices)]  # Alternate oui/non
        votes.append((nas, code, law_id, vote))

        if (i + 1) % 10000 == 0:
            print(f"  Generated {i + 1:,} credentials...")

    return votes

def calculate_hash(nas: str, code: str, law_id: str) -> str:
    """Calculate vote hash like the ingestion API does."""
    data = f"{nas}|{code}|{law_id}"
    return hashlib.sha256(data.encode()).hexdigest()

def load_hashes_to_redis(votes: List[Tuple[str, str, str, str]]):
    """Load vote hashes into Redis."""
    print("\nConnecting to Redis...")
    r = redis.Redis(
        host='localhost',
        port=6379,
        db=0,
        decode_responses=False
    )

    print("Loading hashes into Redis...")
    start_time = time.time()

    # Use pipeline for better performance
    pipe = r.pipeline()
    batch_size = 1000

    for idx, (nas, code, law_id, vote) in enumerate(votes):
        vote_hash = calculate_hash(nas, code, law_id)
        pipe.sadd('valid_hashes', vote_hash)

        # Execute batch
        if (idx + 1) % batch_size == 0:
            pipe.execute()
            pipe = r.pipeline()
            if (idx + 1) % 10000 == 0:
                elapsed = time.time() - start_time
                rate = (idx + 1) / elapsed
                print(f"  Loaded {idx + 1:,} hashes ({rate:.0f} hashes/s)...")

    # Execute remaining
    pipe.execute()

    elapsed = time.time() - start_time
    total_hashes = r.scard('valid_hashes')

    print(f"\n✅ Loaded {total_hashes:,} unique hashes in {elapsed:.1f}s")
    print(f"   Rate: {total_hashes/elapsed:.0f} hashes/second")

    return votes

def save_test_data(votes: List[Tuple[str, str, str, str]], filename: str = 'test_votes.txt'):
    """Save vote data to file for load test to use."""
    print(f"\nSaving test data to {filename}...")
    with open(filename, 'w') as f:
        for nas, code, law_id, vote in votes:
            f.write(f"{nas}|{code}|{law_id}|{vote}\n")
    print(f"✅ Saved {len(votes):,} vote credentials")

if __name__ == '__main__':
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 100000

    print("="*60)
    print(f"PRE-LOADING {count:,} VALID VOTE HASHES FOR LOAD TEST")
    print("="*60)

    # Generate votes
    votes = generate_vote_data(count)

    # Load to Redis
    votes = load_hashes_to_redis(votes)

    # Save for load test
    save_test_data(votes)

    print("\n" + "="*60)
    print("✅ READY FOR LOAD TEST!")
    print("="*60)
    print("\nRun load test with:")
    print(f"  python3 tests/load_test.py --votes {count} --rate 5000")
