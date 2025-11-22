#!/usr/bin/env python3
"""
Small election test with 17 voters for debugging
Tests election voting: Direct DB insertion or API if available
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

NUM_VOTES = 17
ELECTION_ID = 1
REGION_ID = 1

def run_test():
    """Test election voting with 17 votes"""
    print("\n" + "="*70)
    print(f"SMALL ELECTION TEST - {NUM_VOTES} VOTES")
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

    # Clear previous small test votes
    cur.execute("DELETE FROM election_votes WHERE vote_hash LIKE %s", ('smalltest_%',))
    cur.execute("DELETE FROM election_results WHERE election_id = %s AND region_id = %s", (ELECTION_ID, REGION_ID))
    conn.commit()
    print(f"\n✅ Cleared previous test data")

    # Vote distribution (spread across candidates)
    vote_distribution = {
        candidate_ids[0]: 0.35,  # 35%
        candidate_ids[1]: 0.30 if len(candidate_ids) > 1 else 0,  # 30%
        candidate_ids[2]: 0.20 if len(candidate_ids) > 2 else 0,  # 20%
        candidate_ids[3]: 0.10 if len(candidate_ids) > 3 else 0,  # 10%
        candidate_ids[4]: 0.05 if len(candidate_ids) > 4 else 0,  # 5%
    }

    print(f"\nGenerating and inserting {NUM_VOTES} election votes...")
    start_time = time.time()
    votes_data = []

    for i in range(NUM_VOTES):
        vote_hash = f"smalltest_{i:03d}"

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
            '{"source": "small_election_test", "submitted_at": "' + datetime.now().isoformat() + '"}'
        ))

        # Get candidate name for display
        cand_info = next(c for c in candidates if c[0] == selected_candidate)
        print(f"  Vote {i+1}/17: {cand_info[1]} {cand_info[2]} ({cand_info[3]})")

    # Bulk insert
    cur.executemany("""
        INSERT INTO election_votes (vote_hash, election_id, region_id, candidate_id, metadata)
        VALUES (%s, %s, %s, %s, %s)
    """, votes_data)
    conn.commit()

    # Update election results
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

    duration = time.time() - start_time

    # Get final results
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

    print(f"\n{'='*70}")
    print(f"ELECTION TEST COMPLETE")
    print(f"{'='*70}")
    print(f"Duration: {duration:.2f}s")
    print(f"Rate: {NUM_VOTES/duration:.0f} votes/sec")
    print(f"\n📊 Results:")
    for rank, (fname, lname, party, votes) in enumerate(results, 1):
        percentage = (votes / total_votes * 100) if total_votes > 0 else 0
        icon = "🏆" if rank == 1 else f" {rank}."
        print(f"   {icon} {fname} {lname} ({party}): {votes} votes ({percentage:.1f}%)")

    if total_votes == NUM_VOTES:
        print(f"\n✅ SUCCESS! All {NUM_VOTES} election votes processed correctly!")
    else:
        print(f"\n⚠️  WARNING: Expected {NUM_VOTES} votes but got {total_votes}")

    print(f"{'='*70}\n")

    cur.close()
    conn.close()

def main():
    """Run small election test"""
    print("\n" + "="*70)
    print("SMALL ELECTION DEBUGGING TEST")
    print("Testing with 17 voters")
    print("="*70)

    run_test()

if __name__ == "__main__":
    main()
