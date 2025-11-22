#!/usr/bin/env python3
"""
Load test for election voting - 250k votes for Election ID 1
"""
import psycopg2
import random
import time
from datetime import datetime

# Configuration
POSTGRES_HOST = "localhost"
POSTGRES_PORT = 5432
POSTGRES_DB = "voting"
POSTGRES_USER = "voting_user"
POSTGRES_PASSWORD = "voting_password"

NUM_VOTES = 250000
ELECTION_ID = 1
REGION_ID = 1  # Abitibi-Ouest

def main():
    print("=" * 70)
    print(f"ELECTION VOTE LOAD TEST - {NUM_VOTES:,} VOTES")
    print("=" * 70)

    # Connect to database
    print("\nConnecting to database...")
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

    print(f"\nConfiguration:")
    print(f"   Election ID: {ELECTION_ID}")
    print(f"   Region ID: {REGION_ID}")
    print(f"   Candidates: {len(candidates)}")
    for c in candidates:
        print(f"      - {c[1]} {c[2]} ({c[3]})")

    # Clear previous votes for this test
    print(f"\nClearing previous test votes...")
    cur.execute("DELETE FROM election_votes WHERE election_id = %s AND vote_hash LIKE %s", (ELECTION_ID, 'loadtest_%'))
    cur.execute("DELETE FROM election_results WHERE election_id = %s AND region_id = %s", (ELECTION_ID, REGION_ID))
    conn.commit()

    # Generate votes
    print(f"\nGenerating {NUM_VOTES:,} votes...")

    # Vote distribution (realistic pattern)
    vote_distribution = {
        candidate_ids[0]: 0.40,  # 40%
        candidate_ids[1]: 0.30 if len(candidate_ids) > 1 else 0,  # 30%
        candidate_ids[2]: 0.15 if len(candidate_ids) > 2 else 0,  # 15%
        candidate_ids[3]: 0.10 if len(candidate_ids) > 3 else 0,  # 10%
        candidate_ids[4]: 0.05 if len(candidate_ids) > 4 else 0,  # 5%
    }

    start_time = time.time()

    # Insert votes in batches
    batch_size = 5000
    for batch_start in range(0, NUM_VOTES, batch_size):
        batch_end = min(batch_start + batch_size, NUM_VOTES)
        votes_data = []

        for i in range(batch_start, batch_end):
            # Generate unique hash for each voter
            vote_hash = f"loadtest_{i:07d}"

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
                '{"source": "load_test", "submitted_at": "' + datetime.now().isoformat() + '"}'
            ))

        # Bulk insert
        cur.executemany("""
            INSERT INTO election_votes (vote_hash, election_id, region_id, candidate_id, metadata)
            VALUES (%s, %s, %s, %s, %s)
        """, votes_data)

        conn.commit()

        if (batch_end) % 25000 == 0 or batch_end == NUM_VOTES:
            elapsed = time.time() - start_time
            rate = batch_end / elapsed
            print(f"   ELECTION: {batch_end:,}/{NUM_VOTES:,} votes ({rate:.0f} votes/sec)")

    duration = time.time() - start_time
    rate = NUM_VOTES / duration if duration > 0 else 0

    # Update election results table
    print(f"\nCalculating results...")
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

    # Fetch and display results
    cur.execute("""
        SELECT c.first_name, c.last_name, p.party_code, p.party_color,
               COALESCE(er.vote_count, 0) as votes
        FROM candidates c
        JOIN political_parties p ON c.party_id = p.id
        LEFT JOIN election_results er ON c.id = er.candidate_id
            AND er.election_id = %s AND er.region_id = %s
        WHERE c.election_id = %s AND c.region_id = %s
        ORDER BY votes DESC
    """, (ELECTION_ID, REGION_ID, ELECTION_ID, REGION_ID))

    results = cur.fetchall()
    total_votes = sum(r[4] for r in results)

    print(f"\n{'=' * 70}")
    print(f"ELECTION VOTE TEST COMPLETE")
    print(f"{'=' * 70}")
    print(f"Duration: {duration:.2f}s")
    print(f"Total: {total_votes:,} votes")
    print(f"Rate: {rate:.0f} votes/sec")
    print(f"\nFinal Results:")
    for rank, (fname, lname, party, color, votes) in enumerate(results, 1):
        percentage = (votes / total_votes * 100) if total_votes > 0 else 0
        icon = "🏆" if rank == 1 else f" {rank}."
        print(f"   {icon} {fname} {lname} ({party}): {votes:,} ({percentage:.2f}%)")

    cur.close()
    conn.close()

    print(f"{'=' * 70}\n")

if __name__ == "__main__":
    main()
