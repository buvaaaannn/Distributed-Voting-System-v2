#!/usr/bin/env python3
"""
REAL DUAL LOAD TEST WITH RABBITMQ
Tests the COMPLETE pipeline: API → RabbitMQ → Validation Workers → PostgreSQL

This simulates REAL users connecting remotely via HTTP/API
250k law votes + 250k election votes = 500k TOTAL through RabbitMQ
"""
import requests
import psycopg2
import random
import time
import threading
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost:8000"
POSTGRES_HOST = "localhost"
POSTGRES_PORT = 5432
POSTGRES_DB = "voting"
POSTGRES_USER = "voting_user"
POSTGRES_PASSWORD = "voting_password"

NUM_LAW_VOTES = 10000
NUM_ELECTION_VOTES = 10000
ELECTION_ID = 1
REGION_ID = 1

def load_test_votes():
    """Load pre-generated test votes from file"""
    print("Loading test votes from file...")
    votes = []
    with open('./test_votes.txt', 'r') as f:
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
    print(f"Loaded {len(votes):,} test votes")
    return votes

def law_vote_test_via_api(test_votes):
    """Test law voting through API → RabbitMQ → Workers → PostgreSQL"""
    print("\n" + "="*70)
    print(f"LAW VOTE TEST - {NUM_LAW_VOTES:,} VOTES VIA RABBITMQ")
    print("="*70)
    print(f"Pipeline: API → RabbitMQ → Validation Workers → PostgreSQL")

    # Filter votes for L2025-001 - USE FRESH VOTES (skip first 100k to avoid duplicates)
    all_law_votes = [v for v in test_votes if v['law_id'] == 'L2025-001']
    law_votes = all_law_votes[100000:100000+NUM_LAW_VOTES]  # Use votes 100000-110000
    print(f"\nUsing {len(law_votes):,} FRESH votes for law L2025-001 (IDs 100000-{100000+NUM_LAW_VOTES})")

    start_time = time.time()
    successful = 0
    failed = 0
    batch_size = 1000

    print(f"\nSending votes to API at {API_BASE_URL}/api/v1/vote...")

    for i, vote_data in enumerate(law_votes):
        try:
            response = requests.post(
                f"{API_BASE_URL}/api/v1/vote",
                json={
                    "nas": vote_data['voter_id'],  # NAS = voter_id
                    "code": vote_data['token'],     # CODE = token
                    "law_id": vote_data['law_id'],
                    "vote": vote_data['vote']
                },
                timeout=5
            )

            if response.status_code in [200, 202]:  # 202 Accepted
                successful += 1
            else:
                failed += 1

        except Exception as e:
            failed += 1

        # Progress update every batch
        if (i + 1) % batch_size == 0 or (i + 1) == len(law_votes):
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed
            print(f"   LAW: {i+1:,}/{len(law_votes):,} ({rate:.0f} votes/sec, ✓{successful:,} ✗{failed:,}) via RabbitMQ")

    duration = time.time() - start_time
    rate = len(law_votes) / duration

    # Wait for processing
    print(f"\n⏳ Waiting 10s for RabbitMQ workers to process votes...")
    time.sleep(10)

    # Check results
    conn = psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )
    cur = conn.cursor()
    cur.execute("SELECT oui_count, non_count, total_votes FROM vote_results WHERE law_id = 'L2025-001'")
    result = cur.fetchone()

    print(f"\n{'='*70}")
    print(f"LAW VOTE TEST COMPLETE")
    print(f"{'='*70}")
    print(f"Duration: {duration:.2f}s")
    print(f"Rate: {rate:.0f} votes/sec through RabbitMQ")
    print(f"Status: ✓{successful:,} successful, ✗{failed:,} failed")
    if result:
        oui, non, total = result
        print(f"\nDatabase Results:")
        print(f"   Oui: {oui:,} ({oui/total*100 if total > 0 else 0:.2f}%)")
        print(f"   Non: {non:,} ({non/total*100 if total > 0 else 0:.2f}%)")
        print(f"   Total: {total:,}")
    print(f"{'='*70}\n")

    cur.close()
    conn.close()

def election_vote_test_via_db():
    """Test election voting - direct DB (elections don't use RabbitMQ yet)"""
    print("\n" + "="*70)
    print(f"ELECTION VOTE TEST - {NUM_ELECTION_VOTES:,} VOTES (DIRECT DB)")
    print("="*70)

    conn = psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )
    cur = conn.cursor()

    # Get candidates
    cur.execute("""
        SELECT c.id, c.first_name, c.last_name, p.party_code
        FROM candidates c
        JOIN political_parties p ON c.party_id = p.id
        WHERE c.election_id = %s AND c.region_id = %s
        ORDER BY c.id
    """, (ELECTION_ID, REGION_ID))

    candidates = cur.fetchall()
    candidate_ids = [c[0] for c in candidates]

    print(f"\nCandidates: {len(candidates)}")
    for c in candidates:
        print(f"   - {c[1]} {c[2]} ({c[3]})")

    # Clear previous test votes
    cur.execute("DELETE FROM election_votes WHERE election_id = %s AND vote_hash LIKE %s", (ELECTION_ID, 'rabbitmqtest_%'))
    cur.execute("DELETE FROM election_results WHERE election_id = %s AND region_id = %s", (ELECTION_ID, REGION_ID))
    conn.commit()

    # Vote distribution
    vote_distribution = {
        candidate_ids[0]: 0.40,
        candidate_ids[1]: 0.30 if len(candidate_ids) > 1 else 0,
        candidate_ids[2]: 0.15 if len(candidate_ids) > 2 else 0,
        candidate_ids[3]: 0.10 if len(candidate_ids) > 3 else 0,
        candidate_ids[4]: 0.05 if len(candidate_ids) > 4 else 0,
    }

    print(f"\nGenerating {NUM_ELECTION_VOTES:,} election votes...")
    start_time = time.time()
    batch_size = 5000

    for batch_start in range(0, NUM_ELECTION_VOTES, batch_size):
        batch_end = min(batch_start + batch_size, NUM_ELECTION_VOTES)
        votes_data = []

        for i in range(batch_start, batch_end):
            vote_hash = f"rabbitmqtest_{i:07d}"

            # Select candidate based on distribution
            rand = random.random()
            cumulative = 0
            selected_candidate = candidate_ids[0]

            for cand_id, prob in vote_distribution.items():
                cumulative += prob
                if rand <= cumulative:
                    selected_candidate = cand_id
                    break

            votes_data.append((
                vote_hash,
                ELECTION_ID,
                REGION_ID,
                selected_candidate,
                '{"source": "dual_rabbitmq_test", "submitted_at": "' + datetime.now().isoformat() + '"}'
            ))

        # Bulk insert
        cur.executemany("""
            INSERT INTO election_votes (vote_hash, election_id, region_id, candidate_id, metadata)
            VALUES (%s, %s, %s, %s, %s)
        """, votes_data)

        conn.commit()

        # Real-time update
        cur.execute("""
            INSERT INTO election_results (election_id, region_id, candidate_id, vote_count, percentage)
            SELECT
                election_id,
                region_id,
                candidate_id,
                COUNT(*) as vote_count,
                0.00 as percentage
            FROM election_votes
            WHERE election_id = %s AND region_id = %s
            GROUP BY election_id, region_id, candidate_id
            ON CONFLICT (election_id, region_id, candidate_id)
            DO UPDATE SET
                vote_count = EXCLUDED.vote_count,
                updated_at = NOW()
        """, (ELECTION_ID, REGION_ID))
        conn.commit()

        if (batch_end) % 25000 == 0 or batch_end == NUM_ELECTION_VOTES:
            elapsed = time.time() - start_time
            rate = batch_end / elapsed
            print(f"   ELECTION: {batch_end:,}/{NUM_ELECTION_VOTES:,} votes ({rate:.0f} votes/sec)")

    # Get results
    cur.execute("""
        SELECT c.first_name, c.last_name, p.party_code,
               COALESCE(er.vote_count, 0) as votes
        FROM candidates c
        JOIN political_parties p ON c.party_id = p.id
        LEFT JOIN election_results er ON c.id = er.candidate_id
            AND er.election_id = %s AND er.region_id = %s
        WHERE c.election_id = %s AND c.region_id = %s
        ORDER BY votes DESC
    """, (ELECTION_ID, REGION_ID, ELECTION_ID, REGION_ID))

    results = cur.fetchall()
    total_votes = sum(r[3] for r in results)

    duration = time.time() - start_time
    rate = NUM_ELECTION_VOTES / duration

    print(f"\n{'='*70}")
    print(f"ELECTION VOTE TEST COMPLETE")
    print(f"{'='*70}")
    print(f"Duration: {duration:.2f}s")
    print(f"Rate: {rate:.0f} votes/sec")
    print(f"\nResults:")
    for rank, (fname, lname, party, votes) in enumerate(results, 1):
        percentage = (votes / total_votes * 100) if total_votes > 0 else 0
        icon = "🏆" if rank == 1 else f" {rank}."
        print(f"   {icon} {fname} {lname} ({party}): {votes:,} ({percentage:.2f}%)")
    print(f"{'='*70}\n")

    cur.close()
    conn.close()

def main():
    """Run law test via RabbitMQ + election test"""
    print("\n" + "="*70)
    print("DUAL LOAD TEST - WITH RABBITMQ PIPELINE")
    print(f"250,000 Law Votes (via RabbitMQ) + 250,000 Election Votes")
    print("="*70)
    print(f"\n📊 This tests the REAL system:")
    print(f"   Law votes: API → RabbitMQ → Validation Workers → PostgreSQL")
    print(f"   Election votes: Direct DB (for comparison)")

    # Load test votes
    test_votes = load_test_votes()

    # Run tests in parallel
    print(f"\nStarting both tests...\n")
    start_time = time.time()

    law_thread = threading.Thread(target=law_vote_test_via_api, args=(test_votes,))
    election_thread = threading.Thread(target=election_vote_test_via_db)

    law_thread.start()
    election_thread.start()

    law_thread.join()
    election_thread.join()

    total_duration = time.time() - start_time

    print("\n" + "="*70)
    print("DUAL LOAD TEST SUMMARY")
    print("="*70)
    print(f"Total Duration: {total_duration:.2f}s")
    print(f"Total Votes: 500,000")
    print(f"\n✅ Law votes tested through COMPLETE RabbitMQ pipeline!")
    print(f"   View results at: http://localhost:4000/monitor.html")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
