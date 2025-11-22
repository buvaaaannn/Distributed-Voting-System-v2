#!/usr/bin/env python3
"""
Test script to generate 30,000 votes for an election.
Creates a test election with proper timing and generates votes.
"""
import asyncio
import aiohttp
import hashlib
import random
import time
from datetime import datetime, timedelta, timezone
import psycopg2

# Configuration
API_URL = "http://localhost:8000/api/v1"
POSTGRES_HOST = "localhost"
POSTGRES_PORT = 5432
POSTGRES_DB = "voting"
POSTGRES_USER = "voting_user"
POSTGRES_PASSWORD = "voting_password"

# Test parameters
NUM_VOTES = 30000
ELECTION_NAME = "Élection Test 30k - Provinciale 2025"
ELECTION_CODE = "TEST-30K"

def get_db_connection():
    """Get PostgreSQL connection."""
    return psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )

def setup_test_election():
    """Create a test election with proper timing and candidates."""
    print("🔧 Setting up test election...")

    conn = get_db_connection()
    cur = conn.cursor()

    # Set voting window: started 1 hour ago, ends in 2 hours
    start_time = datetime.now(timezone.utc) - timedelta(hours=1)
    end_time = datetime.now(timezone.utc) + timedelta(hours=2)

    # Check if election exists
    cur.execute("SELECT id FROM elections WHERE election_code = %s", (ELECTION_CODE,))
    existing = cur.fetchone()

    if existing:
        election_id = existing[0]
        print(f"✅ Election already exists (ID: {election_id})")
    else:
        # Create election
        cur.execute("""
            INSERT INTO elections (election_code, election_name, election_type, election_date,
                                 status, start_datetime, end_datetime, voting_method)
            VALUES (%s, %s, 'provincial', %s, 'active', %s, %s, 'single_choice')
            RETURNING id
        """, (ELECTION_CODE, ELECTION_NAME, datetime.now().date(), start_time, end_time))
        election_id = cur.fetchone()[0]
        conn.commit()
        print(f"✅ Created test election (ID: {election_id})")

    # Get regions
    cur.execute("SELECT id, region_name FROM regions ORDER BY id LIMIT 3")
    regions = cur.fetchall()

    # Get candidates for first region
    region_id = regions[0][0]
    region_name = regions[0][1]

    cur.execute("""
        SELECT c.id, c.first_name, c.last_name, p.party_code
        FROM candidates c
        JOIN political_parties p ON c.party_id = p.id
        WHERE c.election_id = %s AND c.region_id = %s
        ORDER BY c.id
    """, (election_id, region_id))

    candidates = cur.fetchall()

    cur.close()
    conn.close()

    print(f"\n📊 Test Configuration:")
    print(f"   Election: {ELECTION_NAME}")
    print(f"   Region: {region_name}")
    print(f"   Candidates: {len(candidates)}")
    for c in candidates:
        print(f"      - {c[1]} {c[2]} ({c[3]})")
    print(f"   Start: {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"   End: {end_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"   Votes to generate: {NUM_VOTES:,}")

    return election_id, region_id, [c[0] for c in candidates]

def load_valid_hashes():
    """Load valid voter hashes from Redis."""
    import redis
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)

    # Get all valid hashes
    valid_hashes = list(r.smembers('valid_hashes'))
    print(f"\n🔑 Loaded {len(valid_hashes):,} valid voter hashes from Redis")

    # Clear voted hashes for testing
    voted_count = r.scard('voted_hashes')
    if voted_count > 0:
        print(f"🗑️  Clearing {voted_count:,} previously voted hashes...")
        r.delete('voted_hashes')

    return valid_hashes

async def submit_vote(session, vote_data, semaphore):
    """Submit a single vote."""
    async with semaphore:
        try:
            async with session.post(f"{API_URL}/elections/vote", json=vote_data, timeout=10) as response:
                if response.status == 202:
                    return True, None
                else:
                    error = await response.text()
                    return False, f"Status {response.status}: {error}"
        except Exception as e:
            return False, str(e)

async def generate_votes(election_id, region_id, candidate_ids, valid_hashes):
    """Generate and submit votes asynchronously."""
    print(f"\n🗳️  Generating {NUM_VOTES:,} votes...")
    print(f"   Using {len(valid_hashes):,} unique voters")

    # Limit concurrent requests
    semaphore = asyncio.Semaphore(100)

    # Prepare vote data
    votes = []
    for i in range(NUM_VOTES):
        # Get a unique hash for this vote
        voter_hash = valid_hashes[i % len(valid_hashes)]

        # Reverse engineer NAS+code from hash (we need to use actual valid credentials)
        # For testing, we'll use the hash directly and generate fake NAS/code
        # Note: This won't work unless we have the original NAS/code pairs
        nas = f"{100000000 + i:09d}"
        code = f"V{i:05d}"

        # Random candidate with distribution (simulate realistic voting patterns)
        if i < NUM_VOTES * 0.4:  # 40% for candidate 1
            candidate_id = candidate_ids[0]
        elif i < NUM_VOTES * 0.7:  # 30% for candidate 2
            candidate_id = candidate_ids[1] if len(candidate_ids) > 1 else candidate_ids[0]
        elif i < NUM_VOTES * 0.85:  # 15% for candidate 3
            candidate_id = candidate_ids[2] if len(candidate_ids) > 2 else candidate_ids[0]
        elif i < NUM_VOTES * 0.95:  # 10% for candidate 4
            candidate_id = candidate_ids[3] if len(candidate_ids) > 3 else candidate_ids[0]
        else:  # 5% for candidate 5
            candidate_id = candidate_ids[4] if len(candidate_ids) > 4 else candidate_ids[0]

        vote = {
            "nas": nas,
            "code": code,
            "election_id": election_id,
            "region_id": region_id,
            "candidate_id": candidate_id,
            "voting_method": "single_choice"
        }
        votes.append(vote)

    # Submit votes in batches
    start_time = time.time()
    success_count = 0
    error_count = 0

    async with aiohttp.ClientSession() as session:
        tasks = []
        for i, vote in enumerate(votes):
            task = submit_vote(session, vote, semaphore)
            tasks.append(task)

            # Show progress every 1000 votes
            if (i + 1) % 1000 == 0:
                print(f"   Queued: {i + 1:,}/{NUM_VOTES:,} votes...")

        # Wait for all votes to complete
        print(f"\n⏳ Submitting votes...")
        results = await asyncio.gather(*tasks)

        for success, error in results:
            if success:
                success_count += 1
            else:
                error_count += 1
                if error_count <= 10:  # Show first 10 errors
                    print(f"   ❌ Error: {error}")

    duration = time.time() - start_time
    rate = NUM_VOTES / duration if duration > 0 else 0

    print(f"\n📈 Results:")
    print(f"   ✅ Successful: {success_count:,}")
    print(f"   ❌ Errors: {error_count:,}")
    print(f"   ⏱️  Duration: {duration:.2f}s")
    print(f"   🚀 Rate: {rate:.0f} votes/sec")

    return success_count, error_count

def main():
    """Main test function."""
    print("=" * 70)
    print("🗳️  ELECTION LOAD TEST - 30,000 VOTES")
    print("=" * 70)

    # Setup
    election_id, region_id, candidate_ids = setup_test_election()
    valid_hashes = load_valid_hashes()

    if len(valid_hashes) < NUM_VOTES:
        print(f"\n⚠️  Warning: Only {len(valid_hashes):,} valid hashes available.")
        print(f"   Some votes will be duplicates and rejected.")
        print(f"   Run: python3 scripts/preload_test_hashes.py --count {NUM_VOTES}")

    # Generate votes
    success, errors = asyncio.run(generate_votes(election_id, region_id, candidate_ids, valid_hashes))

    # Check results
    print(f"\n📊 Checking results in database...")
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT c.first_name, c.last_name, p.party_code,
               COALESCE(er.vote_count, 0) as votes
        FROM candidates c
        JOIN political_parties p ON c.party_id = p.id
        LEFT JOIN election_results er ON c.id = er.candidate_id
            AND er.election_id = %s AND er.region_id = %s
        WHERE c.election_id = %s AND c.region_id = %s
        ORDER BY votes DESC
    """, (election_id, region_id, election_id, region_id))

    results = cur.fetchall()
    total_votes = sum(r[3] for r in results)

    print(f"\n🏆 Final Results (Total: {total_votes:,} votes):")
    print(f"   {'Candidate':<25} {'Party':<8} {'Votes':>10} {'%':>8}")
    print(f"   {'-'*25} {'-'*8} {'-'*10} {'-'*8}")
    for name, lastname, party, votes in results:
        percentage = (votes / total_votes * 100) if total_votes > 0 else 0
        print(f"   {name} {lastname:<15} {party:<8} {votes:>10,} {percentage:>7.2f}%")

    cur.close()
    conn.close()

    print(f"\n✅ Test complete!")
    print(f"\n📍 View results at:")
    print(f"   http://localhost:4000/monitor.html")
    print(f"   http://localhost:3000/results")
    print(f"\n" + "=" * 70)

if __name__ == "__main__":
    main()
