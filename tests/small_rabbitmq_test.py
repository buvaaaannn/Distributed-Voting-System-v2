#!/usr/bin/env python3
"""
Small RabbitMQ test with 17 voters for debugging
Tests the COMPLETE pipeline: API → RabbitMQ → Validation Workers → PostgreSQL

Author: David Marleau
Project: Distributed Voting System - Demo Version
"""
import requests
import psycopg2
import hashlib
import time

# Configuration
API_BASE_URL = "http://localhost:8000"
POSTGRES_HOST = "localhost"
POSTGRES_PORT = 5432
POSTGRES_DB = "voting"
POSTGRES_USER = "voting_user"
POSTGRES_PASSWORD = "voting_password"
LAW_ID = "L2025-001"

def load_test_votes():
    """Load 17 test votes from small file"""
    print("Loading test votes from test_votes_small.txt...")
    votes = []
    with open('./test_votes_small.txt', 'r') as f:
        for line in f:
            parts = line.strip().split('|')
            if len(parts) == 4:
                voter_id, token, law_id, vote = parts
                votes.append({
                    'voter_id': voter_id,
                    'token': token,
                    'law_id': law_id,
                    'vote': vote
                })
    print(f"Loaded {len(votes)} test votes")
    return votes

def preload_hashes(votes):
    """Pre-load vote hashes into Redis"""
    import redis
    print("\nPre-loading hashes into Redis...")
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)

    for vote_data in votes:
        hash_val = hashlib.sha256(
            f"{vote_data['voter_id']}|{vote_data['token']}|{vote_data['law_id']}".encode()
        ).hexdigest()
        r.sadd('valid_hashes', hash_val)
        print(f"  Added hash for {vote_data['voter_id']}: {hash_val[:16]}...")

    count = r.scard('valid_hashes')
    print(f"✅ Pre-loaded {count} hashes into Redis")

def run_test(votes):
    """Send votes through RabbitMQ pipeline and check results"""
    print(f"\n{'='*70}")
    print(f"SMALL RABBITMQ TEST - {len(votes)} VOTES")
    print(f"{'='*70}")
    print(f"Pipeline: API → RabbitMQ → Validation Workers → PostgreSQL\n")

    start_time = time.time()
    successful = 0
    failed = 0

    print("Sending votes to API...")
    for i, vote_data in enumerate(votes):
        try:
            response = requests.post(
                f"{API_BASE_URL}/api/v1/vote",
                json={
                    "nas": vote_data['voter_id'],
                    "code": vote_data['token'],
                    "law_id": vote_data['law_id'],
                    "vote": vote_data['vote']
                },
                timeout=5
            )

            if response.status_code in [200, 202]:
                successful += 1
                print(f"  ✓ Vote {i+1}/{len(votes)}: {vote_data['voter_id']} - {vote_data['vote']} (HTTP {response.status_code})")
            else:
                failed += 1
                print(f"  ✗ Vote {i+1}/{len(votes)}: {vote_data['voter_id']} - FAILED (HTTP {response.status_code}): {response.text}")

        except Exception as e:
            failed += 1
            print(f"  ✗ Vote {i+1}/{len(votes)}: {vote_data['voter_id']} - ERROR: {e}")

    duration = time.time() - start_time

    # Wait for processing
    print(f"\n⏳ Waiting 5s for RabbitMQ workers to process votes...")
    time.sleep(5)

    # Check results in database
    conn = psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )
    cur = conn.cursor()
    cur.execute("SELECT oui_count, non_count, total_votes FROM vote_results WHERE law_id = %s", (LAW_ID,))
    result = cur.fetchone()

    print(f"\n{'='*70}")
    print(f"TEST COMPLETE")
    print(f"{'='*70}")
    print(f"Duration: {duration:.2f}s")
    print(f"API Status: ✓{successful} successful, ✗{failed} failed")

    if result:
        oui, non, total = result
        print(f"\n📊 Database Results:")
        print(f"   Oui: {oui} ({oui/total*100 if total > 0 else 0:.1f}%)")
        print(f"   Non: {non} ({non/total*100 if total > 0 else 0:.1f}%)")
        print(f"   Total: {total}")

        if total == len(votes):
            print(f"\n✅ SUCCESS! All {len(votes)} votes processed correctly through RabbitMQ pipeline!")
        else:
            print(f"\n⚠️  WARNING: Expected {len(votes)} votes but got {total} in database")
    else:
        print(f"\n❌ ERROR: No results found in database")

    print(f"{'='*70}\n")

    cur.close()
    conn.close()

def main():
    """Run small test"""
    print("\n" + "="*70)
    print("SMALL RABBITMQ DEBUGGING TEST")
    print("Testing with 17 voters")
    print("="*70)

    # Load votes
    votes = load_test_votes()

    # Pre-load hashes
    preload_hashes(votes)

    # Run test
    run_test(votes)

if __name__ == "__main__":
    main()
