#!/usr/bin/env python3
"""
Sanity Check Test - 75 Votes
Tests the COMPLETE system with both law voting and elections

Author: David Marleau
Project: Distributed Voting System - Demo Version
"""
import requests
import psycopg2
import redis
import hashlib
import time
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost:8000"
POSTGRES_HOST = "localhost"
POSTGRES_PORT = 5432
POSTGRES_DB = "voting"
POSTGRES_USER = "voting_user"
POSTGRES_PASSWORD = "voting_password"

# Test data
LAW_VOTES = 40  # 40 law votes
ELECTION_VOTES = 35  # 35 election votes
TOTAL_VOTES = LAW_VOTES + ELECTION_VOTES

def print_header(message):
    """Print formatted header"""
    print("\n" + "="*70)
    print(message)
    print("="*70 + "\n")

def clean_database():
    """Clean previous test data"""
    print("🧹 Cleaning database...")
    conn = psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )
    cursor = conn.cursor()

    # Clean law votes
    cursor.execute("DELETE FROM vote_audit WHERE law_id = 'L2025-001'")
    cursor.execute("DELETE FROM duplicate_attempts WHERE law_id = 'L2025-001'")

    # Clean election votes
    cursor.execute("DELETE FROM election_votes WHERE election_id = 1")
    cursor.execute("DELETE FROM election_results WHERE election_id = 1")

    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Database cleaned")

def preload_hashes():
    """Pre-load vote hashes into Redis"""
    print(f"📦 Pre-loading {TOTAL_VOTES} vote hashes into Redis...")
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)

    # Clear existing hashes
    r.delete('valid_hashes')

    # Pre-load law vote hashes
    for i in range(LAW_VOTES):
        nas = f"{i:09d}"
        code = f"T{i:05d}"
        law_id = "L2025-001"
        hash_val = hashlib.sha256(f"{nas}|{code}|{law_id}".encode()).hexdigest()
        r.sadd('valid_hashes', hash_val)

    # Pre-load election vote hashes (using offset to avoid duplicates)
    for i in range(ELECTION_VOTES):
        voter_id = LAW_VOTES + i
        nas = f"{voter_id:09d}"
        code = f"T{voter_id:05d}"
        # Hash for elections doesn't include law_id, just nas|code
        hash_val = hashlib.sha256(f"{nas}|{code}".encode()).hexdigest()
        r.sadd('valid_hashes', hash_val)

    total = r.scard('valid_hashes')
    print(f"✅ Loaded {total} hashes into Redis")

def submit_law_votes():
    """Submit law votes via API"""
    print(f"\n📊 Submitting {LAW_VOTES} law votes...")

    success_count = 0
    error_count = 0

    for i in range(LAW_VOTES):
        nas = f"{i:09d}"
        code = f"T{i:05d}"
        vote = "oui" if i % 3 != 0 else "non"  # ~67% oui, ~33% non

        payload = {
            "nas": nas,
            "code": code,
            "law_id": "L2025-001",
            "vote": vote
        }

        try:
            response = requests.post(f"{API_BASE_URL}/api/v1/vote", json=payload, timeout=5)
            if response.status_code == 200:
                success_count += 1
                print(f"  ✓ Vote {i+1}/{LAW_VOTES}: {vote.upper()}")
            else:
                error_count += 1
                print(f"  ✗ Vote {i+1}/{LAW_VOTES} failed: {response.status_code}")
        except Exception as e:
            error_count += 1
            print(f"  ✗ Vote {i+1}/{LAW_VOTES} error: {e}")

    print(f"\n📈 Law Votes Summary: {success_count} submitted, {error_count} errors")
    return success_count

def submit_election_votes():
    """Submit election votes via API"""
    print(f"\n🗳️  Submitting {ELECTION_VOTES} election votes...")

    success_count = 0
    error_count = 0

    # Distribute votes across 5 candidates
    candidates = [1, 2, 3, 4, 5]

    for i in range(ELECTION_VOTES):
        voter_id = LAW_VOTES + i
        nas = f"{voter_id:09d}"
        code = f"T{voter_id:05d}"

        # Distribute votes: CAQ gets most, then PLQ, PQ, QS, PCQ
        if i % 5 == 0:
            candidate_id = 1  # CAQ - Gabrielle Savois
        elif i % 5 == 1:
            candidate_id = 1  # CAQ
        elif i % 5 == 2:
            candidate_id = 2  # PLQ - Jean Tremblay
        elif i % 5 == 3:
            candidate_id = 3  # PQ - Marie Gagnon
        else:
            candidate_id = 4  # QS - Pierre Côté

        payload = {
            "nas": nas,
            "code": code,
            "election_id": 1,
            "region_id": 1,
            "candidate_id": candidate_id,
            "voting_method": "single_choice"
        }

        try:
            response = requests.post(f"{API_BASE_URL}/api/v1/elections/vote", json=payload, timeout=5)
            if response.status_code == 200:
                success_count += 1
                print(f"  ✓ Vote {i+1}/{ELECTION_VOTES}: Candidate {candidate_id}")
            else:
                error_count += 1
                print(f"  ✗ Vote {i+1}/{ELECTION_VOTES} failed: {response.status_code}")
        except Exception as e:
            error_count += 1
            print(f"  ✗ Vote {i+1}/{ELECTION_VOTES} error: {e}")

    print(f"\n📈 Election Votes Summary: {success_count} submitted, {error_count} errors")
    return success_count

def wait_for_processing():
    """Wait for votes to be processed through RabbitMQ"""
    print("\n⏳ Waiting for RabbitMQ to process votes (10 seconds)...")
    time.sleep(10)
    print("✅ Processing wait complete")

def verify_law_results():
    """Verify law voting results in database"""
    print("\n🔍 Verifying law vote results...")

    conn = psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )
    cursor = conn.cursor()

    cursor.execute("""
        SELECT law_id, vote, COUNT(*) as count
        FROM vote_audit
        WHERE law_id = 'L2025-001'
        GROUP BY law_id, vote
        ORDER BY vote
    """)

    results = cursor.fetchall()

    total = 0
    oui_count = 0
    non_count = 0

    for row in results:
        law_id, vote, count = row
        total += count
        if vote == 'oui':
            oui_count = count
        else:
            non_count = count
        print(f"  {vote.upper()}: {count} votes")

    cursor.close()
    conn.close()

    oui_pct = (oui_count / total * 100) if total > 0 else 0
    non_pct = (non_count / total * 100) if total > 0 else 0

    print(f"\n  Total: {total} votes")
    print(f"  OUI: {oui_pct:.1f}% | NON: {non_pct:.1f}%")

    return total

def verify_election_results():
    """Verify election results in database"""
    print("\n🔍 Verifying election results...")

    conn = psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            c.first_name,
            c.last_name,
            p.party_code,
            COUNT(ev.id) as vote_count
        FROM election_votes ev
        JOIN candidates c ON ev.candidate_id = c.id
        JOIN political_parties p ON c.party_id = p.id
        WHERE ev.election_id = 1 AND ev.region_id = 1
        GROUP BY c.first_name, c.last_name, p.party_code
        ORDER BY vote_count DESC
    """)

    results = cursor.fetchall()
    total = 0

    for i, row in enumerate(results):
        first_name, last_name, party, votes = row
        total += votes
        icon = "🏆" if i == 0 else " "
        print(f"  {icon} {first_name} {last_name} ({party}): {votes} votes")

    cursor.close()
    conn.close()

    print(f"\n  Total: {total} votes")
    return total

def main():
    """Run sanity check test"""
    print_header("🔬 SANITY CHECK TEST - 75 VOTES")
    print(f"Testing: {LAW_VOTES} law votes + {ELECTION_VOTES} election votes = {TOTAL_VOTES} total")

    start_time = time.time()

    # Step 1: Clean database
    clean_database()

    # Step 2: Pre-load hashes
    preload_hashes()

    # Step 3: Submit law votes
    law_submitted = submit_law_votes()

    # Step 4: Submit election votes
    election_submitted = submit_election_votes()

    # Step 5: Wait for processing
    wait_for_processing()

    # Step 6: Verify results
    print_header("📊 VERIFICATION RESULTS")

    law_processed = verify_law_results()
    election_processed = verify_election_results()

    # Final summary
    duration = time.time() - start_time

    print_header("✅ SANITY CHECK COMPLETE")
    print(f"Duration: {duration:.1f}s")
    print(f"\nLaw Votes:")
    print(f"  Submitted: {law_submitted}/{LAW_VOTES}")
    print(f"  Processed: {law_processed}/{LAW_VOTES}")
    print(f"\nElection Votes:")
    print(f"  Submitted: {election_submitted}/{ELECTION_VOTES}")
    print(f"  Processed: {election_processed}/{ELECTION_VOTES}")
    print(f"\nTotal:")
    print(f"  Submitted: {law_submitted + election_submitted}/{TOTAL_VOTES}")
    print(f"  Processed: {law_processed + election_processed}/{TOTAL_VOTES}")

    # Success check
    if law_processed == LAW_VOTES and election_processed == ELECTION_VOTES:
        print("\n🎉 SUCCESS! All votes processed correctly!")
        print("\n🌐 View results:")
        print(f"  • Voting UI: http://localhost:3000/results")
        print(f"  • Monitor Dashboard: http://localhost:4000/monitor.html")
        return 0
    else:
        print(f"\n❌ FAILURE! Expected {TOTAL_VOTES} votes, got {law_processed + election_processed}")
        return 1

if __name__ == "__main__":
    exit(main())
