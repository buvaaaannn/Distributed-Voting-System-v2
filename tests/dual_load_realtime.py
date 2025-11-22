#!/usr/bin/env python3
"""
Simultaneous load test with REAL-TIME updates: 250k law votes + 250k election votes
Tests system under dual concurrent load with live progress in monitor dashboard
"""
import psycopg2
import random
import time
import threading
import hashlib
from datetime import datetime

# Configuration
POSTGRES_HOST = "localhost"
POSTGRES_PORT = 5432
POSTGRES_DB = "voting"
POSTGRES_USER = "voting_user"
POSTGRES_PASSWORD = "voting_password"

NUM_VOTES = 250000
ELECTION_ID = 1
REGION_ID = 1
LAW_ID = "thisisworking"
UPDATE_INTERVAL = 5000  # Update results every 5k votes for real-time monitoring

def law_vote_test():
    """Test law voting - 250k votes with REAL-TIME updates"""
    print("\n" + "="*70)
    print(f"LAW VOTE TEST - {NUM_VOTES:,} VOTES FOR '{LAW_ID}' (REAL-TIME)")
    print("="*70)

    conn = psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )
    cur = conn.cursor()

    # Clear previous votes
    cur.execute("DELETE FROM vote_audit WHERE law_id = %s AND metadata->>'source' = 'dual_load_test_realtime'", (LAW_ID,))
    cur.execute("UPDATE vote_results SET oui_count = 0, non_count = 0, total_votes = 0 WHERE law_id = %s", (LAW_ID,))
    conn.commit()

    print(f"\nGenerating {NUM_VOTES:,} law votes with real-time updates...")
    start_time = time.time()
    batch_size = 5000

    for batch_start in range(0, NUM_VOTES, batch_size):
        batch_end = min(batch_start + batch_size, NUM_VOTES)
        votes_data = []

        for i in range(batch_start, batch_end):
            # Generate proper 64-character SHA-256 hash
            vote_hash = hashlib.sha256(f"lawtest_{i:07d}_{LAW_ID}".encode()).hexdigest()
            vote = random.choice(['oui', 'non'])
            now = datetime.now()

            votes_data.append((
                vote_hash,
                LAW_ID,
                vote,
                'validated',  # Use 'validated' status (matches schema constraint)
                now,  # timestamp field (required, NOT NULL)
                '{"source": "dual_load_test_realtime", "submitted_at": "' + now.isoformat() + '"}'
            ))

        # Bulk insert with timestamp field
        cur.executemany("""
            INSERT INTO vote_audit (vote_hash, law_id, vote, status, timestamp, metadata)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, votes_data)

        conn.commit()

        # REAL-TIME UPDATE: Update vote_results after every batch
        cur.execute("""
            UPDATE vote_results SET
                oui_count = (SELECT COUNT(*) FROM vote_audit WHERE law_id = %s AND vote = 'oui' AND metadata->>'source' = 'dual_load_test_realtime'),
                non_count = (SELECT COUNT(*) FROM vote_audit WHERE law_id = %s AND vote = 'non' AND metadata->>'source' = 'dual_load_test_realtime'),
                total_votes = (SELECT COUNT(*) FROM vote_audit WHERE law_id = %s AND metadata->>'source' = 'dual_load_test_realtime')
            WHERE law_id = %s
        """, (LAW_ID, LAW_ID, LAW_ID, LAW_ID))
        conn.commit()

        if (batch_end) % 25000 == 0 or batch_end == NUM_VOTES:
            elapsed = time.time() - start_time
            rate = batch_end / elapsed
            print(f"   LAW: {batch_end:,}/{NUM_VOTES:,} votes ({rate:.0f} votes/sec) ✅ Results updated in monitor")

    # Get final results
    cur.execute("SELECT oui_count, non_count, total_votes FROM vote_results WHERE law_id = %s", (LAW_ID,))
    result = cur.fetchone()

    if result:
        oui, non, total = result
    else:
        oui, non, total = 0, 0, 0

    duration = time.time() - start_time
    rate = NUM_VOTES / duration

    print(f"\n{'='*70}")
    print(f"LAW VOTE TEST COMPLETE")
    print(f"{'='*70}")
    print(f"Duration: {duration:.2f}s")
    print(f"Rate: {rate:.0f} votes/sec")
    print(f"\nResults:")
    if total > 0:
        print(f"   Oui: {oui:,} ({oui/total*100:.2f}%)")
        print(f"   Non: {non:,} ({non/total*100:.2f}%)")
        print(f"   Total: {total:,}")
    else:
        print(f"   No results found")
    print(f"{'='*70}\n")

    cur.close()
    conn.close()

def election_vote_test():
    """Test election voting - 250k votes with REAL-TIME updates"""
    print("\n" + "="*70)
    print(f"ELECTION VOTE TEST - {NUM_VOTES:,} VOTES (REAL-TIME)")
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
    cur.execute("DELETE FROM election_votes WHERE election_id = %s AND vote_hash LIKE %s", (ELECTION_ID, 'elecloadtest_%'))
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

    print(f"\nGenerating {NUM_VOTES:,} election votes with real-time updates...")
    start_time = time.time()
    batch_size = 5000

    for batch_start in range(0, NUM_VOTES, batch_size):
        batch_end = min(batch_start + batch_size, NUM_VOTES)
        votes_data = []

        for i in range(batch_start, batch_end):
            vote_hash = f"elecloadtest_{i:07d}"

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
                '{"source": "dual_load_test_realtime", "submitted_at": "' + datetime.now().isoformat() + '"}'
            ))

        # Bulk insert
        cur.executemany("""
            INSERT INTO election_votes (vote_hash, election_id, region_id, candidate_id, metadata)
            VALUES (%s, %s, %s, %s, %s)
        """, votes_data)

        conn.commit()

        # REAL-TIME UPDATE: Update election_results after every batch
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

        if (batch_end) % 25000 == 0 or batch_end == NUM_VOTES:
            elapsed = time.time() - start_time
            rate = batch_end / elapsed
            print(f"   ELECTION: {batch_end:,}/{NUM_VOTES:,} votes ({rate:.0f} votes/sec) ✅ Results updated in monitor")

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

    duration = time.time() - start_time
    rate = NUM_VOTES / duration

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
    """Run both tests simultaneously with real-time updates"""
    print("\n" + "="*70)
    print("DUAL CONCURRENT LOAD TEST - REAL-TIME MONITORING")
    print(f"250,000 Law Votes + 250,000 Election Votes = 500,000 TOTAL")
    print(f"Results update every {UPDATE_INTERVAL:,} votes in monitor dashboard")
    print("="*70)

    # Create threads for simultaneous execution
    law_thread = threading.Thread(target=law_vote_test)
    election_thread = threading.Thread(target=election_vote_test)

    # Start both tests simultaneously
    print("\nStarting both tests in parallel...\n")
    start_time = time.time()

    law_thread.start()
    election_thread.start()

    # Wait for both to complete
    law_thread.join()
    election_thread.join()

    total_duration = time.time() - start_time

    print("\n" + "="*70)
    print("DUAL LOAD TEST SUMMARY")
    print("="*70)
    print(f"Total Duration: {total_duration:.2f}s")
    print(f"Total Votes: 500,000")
    print(f"Combined Rate: {500000/total_duration:.0f} votes/sec")
    print(f"\n✅ Both systems tested simultaneously with REAL-TIME updates!")
    print(f"   View live results at: http://localhost:4000/monitor.html")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
