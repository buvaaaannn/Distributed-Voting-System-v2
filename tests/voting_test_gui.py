"""
Interactive Testing GUI for Voting System

Features:
- Load testing with configurable vote counts AND ERROR INJECTION
- Database reset functionality
- Error injection (scrambled data, invalid hashes, duplicates) - WORKING
- Manual vote submission
- Autofill from valid hashes
- Live monitoring
- Queue management
"""

import streamlit as st
import requests
import redis
import psycopg2
import random
import hashlib
import time
import pandas as pd
import json
import asyncio
import aiohttp
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import threading

# Page config
st.set_page_config(
    page_title="Voting System Test GUI",
    page_icon="🗳️",
    layout="wide"
)

# Configuration
API_URL = "http://localhost:8000"
RABBITMQ_URL = "http://localhost:15672"
RABBITMQ_USER = "guest"
RABBITMQ_PASS = "guest"
REDIS_HOST = "localhost"
REDIS_PORT = 6379
POSTGRES_HOST = "localhost"
POSTGRES_PORT = 5432
POSTGRES_DB = "voting"
POSTGRES_USER = "voting_user"
POSTGRES_PASSWORD = "voting_password"

# Initialize session state
if 'test_results' not in st.session_state:
    st.session_state.test_results = []
if 'valid_hashes' not in st.session_state:
    st.session_state.valid_hashes = []
if 'load_test_running' not in st.session_state:
    st.session_state.load_test_running = False
if 'load_test_stats' not in st.session_state:
    st.session_state.load_test_stats = {'total': 0, 'success': 0, 'failed': 0}

def get_redis_connection():
    """Get Redis connection."""
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

def get_postgres_connection():
    """Get PostgreSQL connection."""
    return psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )

def reset_database():
    """Reset vote database to zero (including voted_hashes)."""
    try:
        # Clear PostgreSQL
        conn = get_postgres_connection()
        cur = conn.cursor()

        # Reset vote results
        cur.execute("TRUNCATE TABLE vote_results RESTART IDENTITY CASCADE;")
        cur.execute("TRUNCATE TABLE vote_audit RESTART IDENTITY CASCADE;")
        cur.execute("TRUNCATE TABLE duplicate_attempts RESTART IDENTITY CASCADE;")

        conn.commit()
        cur.close()
        conn.close()

        # Clear Redis voted_hashes
        r = get_redis_connection()
        r.delete('voted_hashes')

        return True, "✅ Database AND voted_hashes cleared successfully!"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def clear_voted_hashes():
    """Clear only the voted_hashes set in Redis."""
    try:
        r = get_redis_connection()
        count = r.scard('voted_hashes')
        r.delete('voted_hashes')
        return True, f"✅ Cleared {count:,} voted hashes from Redis!"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def purge_review_queue():
    """Purge the review queue in RabbitMQ."""
    try:
        response = requests.delete(
            f"{RABBITMQ_URL}/api/queues/%2F/votes.review/contents",
            auth=(RABBITMQ_USER, RABBITMQ_PASS)
        )
        if response.status_code == 204:
            return True, "✅ Review queue purged successfully!"
        else:
            return False, f"❌ Failed: HTTP {response.status_code}"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def purge_all_queues():
    """Purge all vote queues in RabbitMQ."""
    try:
        queues = ['votes.validation', 'votes.aggregation', 'votes.review']
        for queue in queues:
            requests.delete(
                f"{RABBITMQ_URL}/api/queues/%2F/{queue}/contents",
                auth=(RABBITMQ_USER, RABBITMQ_PASS)
            )
        return True, "✅ All queues purged successfully!"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def get_vote_counts():
    """Get current vote counts from database."""
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        cur.execute("SELECT law_id, oui_count, non_count, total_votes FROM vote_results ORDER BY law_id;")
        results = cur.fetchall()
        cur.close()
        conn.close()

        if results:
            return pd.DataFrame(results, columns=['Law ID', 'OUI', 'NON', 'Total'])
        return pd.DataFrame(columns=['Law ID', 'OUI', 'NON', 'Total'])
    except Exception as e:
        st.error(f"Error fetching vote counts: {e}")
        return pd.DataFrame(columns=['Law ID', 'OUI', 'NON', 'Total'])

def load_valid_hashes():
    """Load valid hashes from Redis."""
    try:
        r = get_redis_connection()
        # Get sample of valid hashes (first 100)
        hashes = list(r.sscan_iter('valid_hashes', count=100))
        return hashes[:100] if hashes else []
    except Exception as e:
        st.error(f"Error loading valid hashes: {e}")
        return []

def get_nas_code_from_file(hash_value):
    """Get NAS and code for a given hash from test_votes.txt."""
    try:
        with open('test_votes.txt', 'r') as f:
            for line in f:
                parts = line.strip().split('|')
                if len(parts) == 4:
                    nas, code, law_id, vote = parts
                    # Compute hash
                    computed_hash = hashlib.sha256(f"{nas}{code}".encode()).hexdigest()
                    if computed_hash == hash_value:
                        return nas, code
        return None, None
    except Exception as e:
        st.error(f"Error reading test votes file: {e}")
        return None, None

def load_test_votes_from_file(count):
    """Load test votes from file."""
    votes = []
    try:
        with open('test_votes.txt', 'r') as f:
            for i, line in enumerate(f):
                if i >= count:
                    break
                parts = line.strip().split('|')
                if len(parts) == 4:
                    nas, code, law_id, vote = parts
                    votes.append({
                        'nas': nas,
                        'code': code,
                        'law_id': law_id,
                        'vote': vote
                    })
        return votes
    except Exception as e:
        st.error(f"Error loading test votes: {e}")
        return []

def generate_scrambled_data():
    """Generate scrambled/invalid NAS and code."""
    scrambled_nas = f"{random.randint(0, 999999999):09d}"
    scrambled_code = f"INVALID{random.randint(0, 99999):05d}"
    return scrambled_nas, scrambled_code

def submit_vote(nas, code, law_id, vote_choice):
    """Submit a single vote."""
    try:
        response = requests.post(
            f"{API_URL}/api/v1/vote",
            json={
                "nas": nas,
                "code": code,
                "law_id": law_id,
                "vote": vote_choice
            },
            timeout=5
        )
        return response.status_code, response.json() if response.status_code in [200, 202] else response.text
    except Exception as e:
        return 500, str(e)

def submit_votes_batch(votes, progress_bar, status_text):
    """Submit votes in batch with progress tracking."""
    total = len(votes)
    success_count = 0
    failed_count = 0

    for i, vote in enumerate(votes):
        status_code, response = submit_vote(
            vote['nas'],
            vote['code'],
            vote['law_id'],
            vote['vote']
        )

        if status_code in [200, 202]:
            success_count += 1
        else:
            failed_count += 1

        # Update progress
        if (i + 1) % 100 == 0 or (i + 1) == total:
            progress = (i + 1) / total
            progress_bar.progress(progress)
            status_text.text(f"Progress: {i+1:,}/{total:,} votes ({success_count:,} success, {failed_count:,} failed)")

    return success_count, failed_count

def export_vote_audit(format='csv', limit=None):
    """Export vote audit log to file."""
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()

        query = """
            SELECT id, vote_hash, law_id, vote, status, timestamp,
                   processed_at, error_message, metadata
            FROM vote_audit
            ORDER BY processed_at DESC
        """

        if limit:
            query += f" LIMIT {limit}"

        cur.execute(query)
        rows = cur.fetchall()
        columns = ['id', 'vote_hash', 'law_id', 'vote', 'status', 'timestamp', 'processed_at', 'error_message', 'metadata']

        cur.close()
        conn.close()

        if format == 'csv':
            df = pd.DataFrame(rows, columns=columns)
            return df.to_csv(index=False), 'vote_audit.csv'
        else:  # JSON
            data = [dict(zip(columns, row)) for row in rows]
            # Convert datetime objects to strings
            for item in data:
                for key, value in item.items():
                    if isinstance(value, datetime):
                        item[key] = value.isoformat()
            return json.dumps(data, indent=2, default=str), 'vote_audit.json'

    except Exception as e:
        st.error(f"Error exporting vote audit: {e}")
        return None, None

def export_duplicate_stats(format='csv'):
    """Export duplicate attempt statistics from Redis."""
    try:
        r = get_redis_connection()

        # Get all duplicate counters
        duplicate_keys = r.keys('duplicate_count:*')

        duplicates = []
        for key in duplicate_keys:
            voter_hash = key.replace('duplicate_count:', '')
            count = int(r.get(key))
            duplicates.append({
                'voter_hash': voter_hash,
                'attempt_count': count
            })

        # Sort by attempt count (highest first)
        duplicates.sort(key=lambda x: x['attempt_count'], reverse=True)

        if format == 'csv':
            df = pd.DataFrame(duplicates)
            return df.to_csv(index=False), 'duplicate_attempts.csv'
        else:  # JSON
            return json.dumps(duplicates, indent=2), 'duplicate_attempts.json'

    except Exception as e:
        st.error(f"Error exporting duplicate stats: {e}")
        return None, None

def export_error_patterns(format='csv'):
    """Export error pattern statistics from Redis."""
    try:
        r = get_redis_connection()

        # Get all error patterns seen
        patterns_seen = list(r.smembers('error_patterns_seen'))

        patterns = []
        for pattern in patterns_seen:
            count = r.get(f'error_pattern:{pattern}')
            count = int(count) if count else 1  # At least 1 if it's in the set

            patterns.append({
                'error_pattern': pattern,
                'occurrence_count': count
            })

        # Sort by occurrence count (highest first)
        patterns.sort(key=lambda x: x['occurrence_count'], reverse=True)

        if format == 'csv':
            df = pd.DataFrame(patterns)
            return df.to_csv(index=False), 'error_patterns.csv'
        else:  # JSON
            return json.dumps(patterns, indent=2), 'error_patterns.json'

    except Exception as e:
        st.error(f"Error exporting error patterns: {e}")
        return None, None

def export_vote_results(format='csv'):
    """Export vote results summary."""
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT law_id, oui_count, non_count, total_votes, created_at, updated_at
            FROM vote_results
            ORDER BY law_id
        """)

        rows = cur.fetchall()
        columns = ['law_id', 'oui_count', 'non_count', 'total_votes', 'created_at', 'updated_at']

        cur.close()
        conn.close()

        if format == 'csv':
            df = pd.DataFrame(rows, columns=columns)
            return df.to_csv(index=False), 'vote_results.csv'
        else:  # JSON
            data = [dict(zip(columns, row)) for row in rows]
            # Convert datetime objects to strings
            for item in data:
                for key, value in item.items():
                    if isinstance(value, datetime):
                        item[key] = value.isoformat()
            return json.dumps(data, indent=2, default=str), 'vote_results.json'

    except Exception as e:
        st.error(f"Error exporting vote results: {e}")
        return None, None

# ═══════════════════════════════════════════════════════════════════════
# ADMIN PANEL FUNCTIONS - Election System Management
# ═══════════════════════════════════════════════════════════════════════

def get_all_elections():
    """Get all elections from database."""
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, election_code, election_name, election_type, election_date, status
            FROM elections
            ORDER BY election_date DESC, id DESC
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return pd.DataFrame(rows, columns=['ID', 'Code', 'Name', 'Type', 'Date', 'Status'])
    except Exception as e:
        st.error(f"Error fetching elections: {e}")
        return pd.DataFrame()

def get_all_regions():
    """Get all regions from database."""
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, region_code, region_name, description FROM regions ORDER BY region_name")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return pd.DataFrame(rows, columns=['ID', 'Code', 'Name', 'Description'])
    except Exception as e:
        st.error(f"Error fetching regions: {e}")
        return pd.DataFrame()

def get_all_parties():
    """Get all political parties from database."""
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, party_code, party_name, party_color FROM political_parties ORDER BY party_name")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return pd.DataFrame(rows, columns=['ID', 'Code', 'Name', 'Color'])
    except Exception as e:
        st.error(f"Error fetching parties: {e}")
        return pd.DataFrame()

def get_candidates_by_election(election_id):
    """Get all candidates for a specific election."""
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT
                c.id, c.first_name, c.last_name,
                r.region_name, p.party_name, p.party_code, c.status
            FROM candidates c
            JOIN regions r ON c.region_id = r.id
            JOIN political_parties p ON c.party_id = p.id
            WHERE c.election_id = %s
            ORDER BY r.region_name, p.party_name
        """, (election_id,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return pd.DataFrame(rows, columns=['ID', 'First Name', 'Last Name', 'Region', 'Party', 'Party Code', 'Status'])
    except Exception as e:
        st.error(f"Error fetching candidates: {e}")
        return pd.DataFrame()

def add_candidate(election_id, region_id, party_id, first_name, last_name):
    """Add a new candidate."""
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO candidates (election_id, region_id, party_id, first_name, last_name, status)
            VALUES (%s, %s, %s, %s, %s, 'active')
            RETURNING id
        """, (election_id, region_id, party_id, first_name, last_name))
        candidate_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return True, f"✅ Candidate added successfully! ID: {candidate_id}"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def add_region(region_code, region_name, description=""):
    """Add a new region."""
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO regions (region_code, region_name, description)
            VALUES (%s, %s, %s)
            RETURNING id
        """, (region_code.upper(), region_name, description))
        region_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return True, f"✅ Region added successfully! ID: {region_id}"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def add_party(party_code, party_name, party_color="#808080"):
    """Add a new political party."""
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO political_parties (party_code, party_name, party_color)
            VALUES (%s, %s, %s)
            RETURNING id
        """, (party_code.upper(), party_name, party_color))
        party_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return True, f"✅ Party added successfully! ID: {party_id}"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def add_election(election_code, election_name, election_type, election_date, start_datetime=None, end_datetime=None, voting_method='single_choice'):
    """Add a new election."""
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO elections (election_code, election_name, election_type, election_date, status, start_datetime, end_datetime, voting_method)
            VALUES (%s, %s, %s, %s, 'draft', %s, %s, %s)
            RETURNING id
        """, (election_code.upper(), election_name, election_type, election_date, start_datetime, end_datetime, voting_method))
        election_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return True, f"✅ Election added successfully! ID: {election_id}"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

# ═══════════════════════════════════════════════════════════════════════
# ELECTION VOTING FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

def get_candidates_by_region_election(election_id, region_id):
    """Get all candidates for a specific election and region."""
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT
                c.id, c.first_name, c.last_name,
                p.party_code, p.party_name, p.party_color,
                c.bio, c.photo_url
            FROM candidates c
            JOIN political_parties p ON c.party_id = p.id
            WHERE c.election_id = %s AND c.region_id = %s AND c.status = 'active'
            ORDER BY p.party_name
        """, (election_id, region_id))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        st.error(f"Error fetching candidates: {e}")
        return []

def submit_election_vote(nas, code, election_id, region_id, candidate_id):
    """Submit a vote for a candidate in an election."""
    try:
        # Compute hash
        vote_hash = hashlib.sha256(f"{nas}{code}".encode()).hexdigest()

        # Check if already voted (using Redis)
        r = get_redis_connection()

        # Check if hash is valid
        if not r.sismember('valid_hashes', vote_hash):
            return 400, {"detail": "Invalid voting credentials"}

        # Check if already voted
        if r.sismember('voted_hashes', vote_hash):
            return 409, {"detail": "You have already voted"}

        # Mark as voted
        r.sadd('voted_hashes', vote_hash)

        # Submit vote to database
        conn = get_postgres_connection()
        cur = conn.cursor()

        # Insert vote
        cur.execute("""
            INSERT INTO election_votes (vote_hash, election_id, region_id, candidate_id, vote_timestamp, processed_at, metadata)
            VALUES (%s, %s, %s, %s, NOW(), NOW(), %s)
            RETURNING id
        """, (vote_hash, election_id, region_id, candidate_id, json.dumps({"source": "test_gui"})))

        vote_id = cur.fetchone()[0]

        # Update election results (increment candidate vote count)
        cur.execute("""
            INSERT INTO election_results (election_id, region_id, candidate_id, vote_count)
            VALUES (%s, %s, %s, 1)
            ON CONFLICT (election_id, region_id, candidate_id)
            DO UPDATE SET vote_count = election_results.vote_count + 1,
                         updated_at = NOW()
        """, (election_id, region_id, candidate_id))

        conn.commit()
        cur.close()
        conn.close()

        return 200, {"message": "Vote recorded successfully", "vote_id": vote_id}

    except Exception as e:
        return 500, {"detail": str(e)}

def get_election_results_by_region(election_id, region_id):
    """Get election results for a specific region."""
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT
                c.first_name, c.last_name,
                p.party_code, p.party_name,
                COALESCE(er.vote_count, 0) as votes
            FROM candidates c
            JOIN political_parties p ON c.party_id = p.id
            LEFT JOIN election_results er ON c.id = er.candidate_id
                AND er.election_id = %s AND er.region_id = %s
            WHERE c.election_id = %s AND c.region_id = %s
            ORDER BY votes DESC, p.party_name
        """, (election_id, region_id, election_id, region_id))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        st.error(f"Error fetching results: {e}")
        return []

# Main GUI
st.title("🗳️ Voting System Test GUI")
st.markdown("---")

# Sidebar - Live Stats
with st.sidebar:
    st.header("📊 Live Statistics")

    if st.button("🔄 Refresh Stats"):
        st.rerun()

    vote_counts = get_vote_counts()
    if not vote_counts.empty:
        st.dataframe(vote_counts, use_container_width=True)
        total_votes = vote_counts['Total'].sum()
        st.metric("Total Votes", f"{total_votes:,}")
    else:
        st.info("No votes yet")

    st.markdown("---")

    # Redis stats
    try:
        r = get_redis_connection()
        valid_count = r.scard('valid_hashes')
        voted_count = r.scard('voted_hashes')
        st.metric("Valid Hashes", f"{valid_count:,}")
        st.metric("Voted Hashes", f"{voted_count:,}")
    except Exception as e:
        st.error(f"Redis error: {e}")

    st.markdown("---")

    # RabbitMQ stats
    try:
        response = requests.get(
            f"{RABBITMQ_URL}/api/queues",
            auth=(RABBITMQ_USER, RABBITMQ_PASS)
        )
        if response.status_code == 200:
            queues = response.json()
            for q in queues:
                if 'votes' in q['name']:
                    st.metric(q['name'], q.get('messages', 0))
    except Exception as e:
        st.warning(f"RabbitMQ: {e}")

# Main content - Tabs
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["🚀 Load Testing", "📝 Manual Vote (Laws)", "🗳️ Election Voting", "🔧 Database Control", "📈 Results", "📥 Audit Export", "⚙️ Admin Panel"])

# Tab 1: Load Testing WITH ERROR INJECTION
with tab1:
    st.header("Load Testing with Error Injection")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Test Configuration")

        num_votes = st.number_input(
            "Number of Votes",
            min_value=1,
            max_value=100000,
            value=1000,
            step=100
        )

    with col2:
        st.subheader("Error Injection")

        enable_errors = st.checkbox("Enable Error Injection")

        if enable_errors:
            error_mode = st.radio(
                "Error Mode",
                ["Percentage", "Fixed Count"]
            )

            if error_mode == "Percentage":
                error_pct = st.slider(
                    "Error Percentage",
                    min_value=0.0,
                    max_value=100.0,
                    value=5.0,
                    step=0.5
                )
                num_errors = int(num_votes * error_pct / 100)
            else:
                num_errors = st.number_input(
                    "Number of Errors",
                    min_value=0,
                    max_value=num_votes,
                    value=50
                )

            st.info(f"Will inject {num_errors} errors out of {num_votes} votes")

            error_types = st.multiselect(
                "Error Types",
                ["Scrambled Data", "Invalid Hash (Not in DB)", "Duplicate Vote"],
                default=["Scrambled Data"]
            )
        else:
            num_errors = 0
            error_types = []

    st.markdown("---")

    if st.button("▶️ Start Load Test with Error Injection", type="primary", use_container_width=True):
        st.info(f"Starting load test with {num_votes:,} votes (including {num_errors} errors)...")

        # Load valid votes
        valid_votes_needed = num_votes - num_errors
        votes = load_test_votes_from_file(valid_votes_needed)

        if len(votes) < valid_votes_needed:
            st.error(f"Not enough test votes! Only {len(votes)} available. Run: python3 scripts/preload_test_hashes.py")
        else:
            # Inject errors
            if enable_errors and num_errors > 0:
                st.write(f"Injecting {num_errors} errors...")

                for i in range(num_errors):
                    error_vote = {
                        'law_id': random.choice(['L2025-001', 'L2025-002', 'L2025-003']),
                        'vote': random.choice(['oui', 'non'])
                    }

                    error_type = random.choice(error_types)

                    if error_type == "Scrambled Data":
                        nas, code = generate_scrambled_data()
                        error_vote['nas'] = nas
                        error_vote['code'] = code
                    elif error_type == "Invalid Hash (Not in DB)":
                        # Generate random hash that's not in valid_hashes
                        error_vote['nas'] = f"{random.randint(0, 999999999):09d}"
                        error_vote['code'] = f"RAND{random.randint(0, 999999):06d}"
                    elif error_type == "Duplicate Vote" and len(votes) > 0:
                        # Copy a valid vote (will be duplicate)
                        dup_vote = random.choice(votes).copy()
                        error_vote = dup_vote

                    votes.append(error_vote)

            # Shuffle to mix errors with valid votes
            random.shuffle(votes)

            # Create progress indicators
            progress_bar = st.progress(0)
            status_text = st.empty()

            # Submit votes
            start_time = time.time()
            success_count, failed_count = submit_votes_batch(votes, progress_bar, status_text)
            duration = time.time() - start_time

            # Show results
            st.success(f"✅ Load test completed in {duration:.2f}s")
            st.json({
                "total_votes": len(votes),
                "successful": success_count,
                "failed": failed_count,
                "duration_seconds": round(duration, 2),
                "rate_per_second": round(len(votes) / duration, 2)
            })

# Tab 2: Manual Vote Submission
with tab2:
    st.header("Manual Vote Submission")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Enter Vote Details")

        # Autofill option
        use_autofill = st.checkbox("🔄 Autofill from Valid Hashes")

        if use_autofill:
            if st.button("Load Valid Hashes"):
                st.session_state.valid_hashes = load_valid_hashes()
                st.success(f"Loaded {len(st.session_state.valid_hashes)} valid hashes")

            if st.session_state.valid_hashes:
                selected_hash = st.selectbox(
                    "Select Valid Hash",
                    st.session_state.valid_hashes
                )

                if selected_hash:
                    nas_val, code_val = get_nas_code_from_file(selected_hash)
                    if nas_val:
                        st.success(f"Found: NAS={nas_val}, CODE={code_val}")
                    else:
                        st.warning("Could not find NAS/CODE for this hash")
                        nas_val = ""
                        code_val = ""
            else:
                nas_val = ""
                code_val = ""
        else:
            nas_val = ""
            code_val = ""

        nas = st.text_input("NAS (9 digits)", value=nas_val, max_chars=9)
        code = st.text_input("Code", value=code_val)

        law_id = st.selectbox(
            "Law ID",
            ["L2025-001", "L2025-002", "L2025-003"]
        )

        vote_choice = st.radio(
            "Vote",
            ["oui", "non"],
            horizontal=True
        )

        # Generate scrambled data option
        if st.button("🎲 Generate Scrambled Data"):
            scrambled_nas, scrambled_code = generate_scrambled_data()
            st.code(f"NAS: {scrambled_nas}\nCODE: {scrambled_code}")
            st.info("Copy these values to the fields above")

    with col2:
        st.subheader("Preview")

        if nas and code:
            vote_hash = hashlib.sha256(f"{nas}{code}".encode()).hexdigest()

            st.json({
                "nas": nas,
                "code": code,
                "law_id": law_id,
                "vote": vote_choice,
                "hash": vote_hash
            })

            # Check if hash is valid
            try:
                r = get_redis_connection()
                is_valid = r.sismember('valid_hashes', vote_hash)
                is_voted = r.sismember('voted_hashes', vote_hash)

                if is_valid:
                    st.success("✅ Valid hash")
                else:
                    st.warning("⚠️ Hash not in valid_hashes set")

                if is_voted:
                    st.error("❌ Already voted!")
                else:
                    st.info("📝 Not voted yet")
            except Exception as e:
                st.error(f"Redis check failed: {e}")

    st.markdown("---")

    if st.button("🗳️ Submit Vote", type="primary", use_container_width=True):
        if not nas or not code:
            st.error("Please enter both NAS and CODE")
        else:
            with st.spinner("Submitting vote..."):
                status_code, response = submit_vote(nas, code, law_id, vote_choice)

                if status_code in [200, 202]:
                    st.success(f"✅ Vote submitted successfully!")
                    st.json(response)

                    # Add to results
                    st.session_state.test_results.append({
                        'timestamp': datetime.now().strftime("%H:%M:%S"),
                        'nas': nas,
                        'law_id': law_id,
                        'vote': vote_choice,
                        'status': status_code,
                        'response': str(response)
                    })
                else:
                    st.error(f"❌ Failed with status {status_code}")
                    st.code(response)

# Tab 3: Election Voting (Vote for Representatives)
with tab3:
    st.header("🗳️ Election Voting - Vote for Your Representative")
    st.info("Select your region and vote for your preferred candidate")

    # Get active elections
    elections_df = get_all_elections()

    if elections_df.empty:
        st.warning("⚠️ No elections available. Please check the Admin Panel.")
    else:
        # Select election
        col1, col2 = st.columns([2, 1])

        with col1:
            selected_election_id = st.selectbox(
                "Select Election",
                options=elections_df['ID'].tolist(),
                format_func=lambda x: f"{elections_df[elections_df['ID']==x]['Name'].values[0]} - {elections_df[elections_df['ID']==x]['Date'].values[0]}",
                key="election_vote_election"
            )

            election_info = elections_df[elections_df['ID']==selected_election_id].iloc[0]
            st.info(f"📅 **{election_info['Name']}** - {election_info['Type'].title()} Election - {election_info['Date']}")

        with col2:
            election_status = election_info['Status']
            if election_status == 'draft':
                st.warning("⚠️ Draft")
            elif election_status == 'active':
                st.success("✅ Active")
            else:
                st.info(f"Status: {election_status}")

        st.markdown("---")

        # Select region
        regions_df = get_all_regions()

        if regions_df.empty:
            st.warning("⚠️ No regions available")
        else:
            selected_region_id = st.selectbox(
                "📍 Your Electoral Region/Circonscription",
                options=regions_df['ID'].tolist(),
                format_func=lambda x: regions_df[regions_df['ID']==x]['Name'].values[0],
                key="election_vote_region",
                help="Select the region where you are eligible to vote"
            )

            region_info = regions_df[regions_df['ID']==selected_region_id].iloc[0]

            st.markdown(f"### Candidates for **{region_info['Name']}**")

            # Get candidates for this region
            candidates = get_candidates_by_region_election(selected_election_id, selected_region_id)

            if not candidates:
                st.warning(f"⚠️ No candidates registered for {region_info['Name']} yet")
            else:
                # Display candidates
                st.markdown("---")

                # Two columns: voting and results
                vote_col, results_col = st.columns([1, 1])

                with vote_col:
                    st.subheader("Cast Your Vote")

                    # NAS and Code input
                    use_autofill_election = st.checkbox("🔄 Autofill from Valid Hashes", key="election_autofill")

                    if use_autofill_election:
                        if st.button("Load Valid Hashes", key="election_load_hashes"):
                            st.session_state.valid_hashes = load_valid_hashes()
                            st.success(f"Loaded {len(st.session_state.valid_hashes)} valid hashes")

                        if st.session_state.valid_hashes:
                            selected_hash = st.selectbox(
                                "Select Valid Hash",
                                st.session_state.valid_hashes,
                                key="election_hash_select"
                            )

                            if selected_hash:
                                nas_val, code_val = get_nas_code_from_file(selected_hash)
                                if nas_val:
                                    st.success(f"Found: NAS={nas_val}, CODE={code_val}")
                                else:
                                    nas_val = ""
                                    code_val = ""
                        else:
                            nas_val = ""
                            code_val = ""
                    else:
                        nas_val = ""
                        code_val = ""

                    nas_election = st.text_input("NAS (9 digits)", value=nas_val, max_chars=9, key="election_nas")
                    code_election = st.text_input("Code", value=code_val, key="election_code")

                    st.markdown("**Select Your Candidate:**")

                    # Display candidates as radio buttons with party colors
                    candidate_options = []
                    for cand in candidates:
                        cand_id, first_name, last_name, party_code, party_name, party_color, bio, photo = cand
                        candidate_options.append({
                            'id': cand_id,
                            'name': f"{first_name} {last_name}",
                            'party_code': party_code,
                            'party_name': party_name,
                            'party_color': party_color
                        })

                    # Create candidate selection
                    selected_candidate_idx = None
                    for idx, cand in enumerate(candidate_options):
                        col_radio, col_info = st.columns([1, 4])
                        with col_radio:
                            if st.radio("", [cand['id']], label_visibility="collapsed", key=f"cand_radio_{cand['id']}"):
                                selected_candidate_idx = idx
                        with col_info:
                            party_badge = f"<span style='background-color:{cand['party_color']}; color:white; padding:4px 12px; border-radius:4px; font-weight:bold; margin-right:8px;'>{cand['party_code']}</span>"
                            st.markdown(f"{party_badge} **{cand['name']}** - {cand['party_name']}", unsafe_allow_html=True)

                    # Simpler selection using selectbox
                    selected_candidate = st.selectbox(
                        "Choose Candidate",
                        options=[c['id'] for c in candidate_options],
                        format_func=lambda x: f"{[c for c in candidate_options if c['id']==x][0]['party_code']} - {[c for c in candidate_options if c['id']==x][0]['name']}",
                        key="election_candidate_select"
                    )

                    selected_cand_info = [c for c in candidate_options if c['id']==selected_candidate][0]
                    st.info(f"Selected: **{selected_cand_info['name']}** ({selected_cand_info['party_code']})")

                    st.markdown("---")

                    if st.button("✅ Submit Vote", type="primary", use_container_width=True, key="submit_election_vote"):
                        if not nas_election or not code_election:
                            st.error("Please enter both NAS and CODE")
                        elif not selected_candidate:
                            st.error("Please select a candidate")
                        else:
                            with st.spinner("Submitting your vote..."):
                                status_code, response = submit_election_vote(
                                    nas_election,
                                    code_election,
                                    selected_election_id,
                                    selected_region_id,
                                    selected_candidate
                                )

                                if status_code == 200:
                                    st.success(f"✅ Your vote for **{selected_cand_info['name']}** has been recorded!")
                                    st.balloons()
                                    time.sleep(1)
                                    st.rerun()
                                elif status_code == 409:
                                    st.error("❌ You have already voted!")
                                elif status_code == 400:
                                    st.error("❌ Invalid voting credentials")
                                else:
                                    st.error(f"❌ Error: {response.get('detail', 'Unknown error')}")

                with results_col:
                    st.subheader("Current Results")
                    st.caption(f"Results for {region_info['Name']}")

                    # Get results
                    results = get_election_results_by_region(selected_election_id, selected_region_id)

                    if results:
                        # Create dataframe
                        results_df = pd.DataFrame(results, columns=['First Name', 'Last Name', 'Party Code', 'Party', 'Votes'])
                        results_df['Candidate'] = results_df['First Name'] + ' ' + results_df['Last Name']

                        # Display as bar chart
                        chart_data = results_df[['Candidate', 'Votes']].set_index('Candidate')
                        st.bar_chart(chart_data)

                        # Display table
                        display_df = results_df[['Party Code', 'Candidate', 'Votes']]
                        st.dataframe(display_df, use_container_width=True, hide_index=True)

                        # Show total
                        total_votes = results_df['Votes'].sum()
                        st.metric("Total Votes Cast", f"{total_votes:,}")
                    else:
                        st.info("No votes cast yet")

# Tab 4: Database Control
with tab4:
    st.header("Database & Queue Control")

    st.warning("⚠️ These operations will modify the database and queues!")

    # Row 1: Database operations
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🔴 Reset Database")
        st.info("This will:\n- Clear all vote results\n- Clear vote audit log\n- Clear duplicate attempts\n- **Clear voted_hashes in Redis**")

        confirm_reset = st.checkbox("I understand this will delete all data", key="reset_confirm")

        if st.button("🔴 Reset Database to Zero", disabled=not confirm_reset, use_container_width=True):
            with st.spinner("Resetting database..."):
                success, message = reset_database()
                if success:
                    st.success(message)
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(message)

    with col2:
        st.subheader("🧹 Clear Voted Hashes")
        st.info("Clear only voted_hashes in Redis\n(keeps vote results in DB)")

        if st.button("🧹 Clear Voted Hashes", use_container_width=True):
            with st.spinner("Clearing voted hashes..."):
                success, message = clear_voted_hashes()
                if success:
                    st.success(message)
                else:
                    st.error(message)

    st.markdown("---")

    # Row 2: Queue operations
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🗑️ Purge Review Queue")
        st.info("Clear votes.review queue\n(invalid/duplicate votes)")

        if st.button("🗑️ Purge Review Queue", use_container_width=True):
            with st.spinner("Purging review queue..."):
                success, message = purge_review_queue()
                if success:
                    st.success(message)
                else:
                    st.error(message)

    with col2:
        st.subheader("💥 Purge All Queues")
        st.info("Clear ALL vote queues:\n- votes.validation\n- votes.aggregation\n- votes.review")

        if st.button("💥 Purge All Queues", use_container_width=True):
            with st.spinner("Purging all queues..."):
                success, message = purge_all_queues()
                if success:
                    st.success(message)
                else:
                    st.error(message)

    st.markdown("---")

    # Row 3: Reload hashes
    st.subheader("🔄 Reload Test Hashes")
    st.info("Regenerate 100,000 valid hashes for testing")

    if st.button("🔄 Reload Test Hashes", use_container_width=True):
        st.code("python3 scripts/preload_test_hashes.py", language="bash")
        st.warning("⚠️ Run this command in your terminal")

    st.markdown("---")

    # Quick stats
    st.subheader("📊 Quick Stats")

    try:
        conn = get_postgres_connection()
        cur = conn.cursor()

        # Get table counts
        cur.execute("SELECT COUNT(*) FROM vote_results;")
        vote_results_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM vote_audit;")
        audit_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM duplicate_attempts;")
        duplicate_count = cur.fetchone()[0]

        cur.close()
        conn.close()

        col1, col2, col3 = st.columns(3)
        col1.metric("Vote Results", vote_results_count)
        col2.metric("Audit Log", audit_count)
        col3.metric("Duplicates", duplicate_count)

    except Exception as e:
        st.error(f"Error fetching stats: {e}")

# Tab 5: Results
with tab5:
    st.header("Test Results")

    if st.session_state.test_results:
        df = pd.DataFrame(st.session_state.test_results)
        st.dataframe(df, use_container_width=True)

        if st.button("Clear Results"):
            st.session_state.test_results = []
            st.rerun()
    else:
        st.info("No test results yet. Submit votes in the 'Manual Vote' tab or run a load test.")

    st.markdown("---")

    st.subheader("Current Vote Distribution")
    vote_counts = get_vote_counts()
    if not vote_counts.empty:
        st.bar_chart(vote_counts.set_index('Law ID')[['OUI', 'NON']])
    else:
        st.info("No votes to display")

# Tab 6: Audit Export
with tab6:
    st.header("📥 Audit & Data Export")
    st.markdown("Export audit logs and statistics to CSV or JSON format for offline analysis.")
    st.info("ℹ️ Files are saved to your Downloads folder. Original data remains in the database.")

    # Export format selection
    col1, col2 = st.columns([1, 3])
    with col1:
        export_format = st.radio("Export Format", ["CSV", "JSON"], horizontal=True)

    st.markdown("---")

    # Section 1: Vote Audit Log
    st.subheader("🗳️ Vote Audit Log")
    st.markdown("Complete audit trail of all validated votes.")

    col1, col2 = st.columns([2, 1])
    with col1:
        # Get audit count
        try:
            conn = get_postgres_connection()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM vote_audit;")
            audit_count = cur.fetchone()[0]
            cur.close()
            conn.close()
            st.metric("Total Audit Records", f"{audit_count:,}")
        except Exception as e:
            st.error(f"Error getting count: {e}")
            audit_count = 0

    with col2:
        limit_audit = st.number_input("Limit rows (0 = all)", min_value=0, max_value=1000000, value=10000, step=1000, key="audit_limit")

    if st.button("📥 Export Vote Audit", use_container_width=True):
        with st.spinner(f"Exporting vote audit to {export_format}..."):
            limit = limit_audit if limit_audit > 0 else None
            data, filename = export_vote_audit(format=export_format.lower(), limit=limit)

            if data and filename:
                st.download_button(
                    label=f"⬇️ Download {filename}",
                    data=data,
                    file_name=filename,
                    mime="text/csv" if export_format == "CSV" else "application/json",
                    use_container_width=True
                )
                st.success(f"✅ {filename} ready for download!")

    st.markdown("---")

    # Section 2: Duplicate Attempts
    st.subheader("🔁 Duplicate Vote Attempts")
    st.markdown("Statistics on duplicate vote attempts (DDoS protection data).")

    try:
        r = get_redis_connection()
        duplicate_keys = r.keys('duplicate_count:*')
        duplicate_count = len(duplicate_keys)
        st.metric("Unique Hashes with Duplicates", f"{duplicate_count:,}")
    except Exception as e:
        st.error(f"Error getting count: {e}")
        duplicate_count = 0

    if st.button("📥 Export Duplicate Stats", use_container_width=True):
        with st.spinner(f"Exporting duplicate stats to {export_format}..."):
            data, filename = export_duplicate_stats(format=export_format.lower())

            if data and filename:
                st.download_button(
                    label=f"⬇️ Download {filename}",
                    data=data,
                    file_name=filename,
                    mime="text/csv" if export_format == "CSV" else "application/json",
                    use_container_width=True
                )
                st.success(f"✅ {filename} ready for download!")

    st.markdown("---")

    # Section 3: Error Patterns
    st.subheader("⚠️ Invalid Hash Error Patterns")
    st.markdown("Unique error patterns detected (DDoS protection data).")

    try:
        r = get_redis_connection()
        patterns_seen = list(r.smembers('error_patterns_seen'))
        pattern_count = len(patterns_seen)
        st.metric("Unique Error Patterns", f"{pattern_count:,}")
    except Exception as e:
        st.error(f"Error getting count: {e}")
        pattern_count = 0

    if st.button("📥 Export Error Patterns", use_container_width=True):
        with st.spinner(f"Exporting error patterns to {export_format}..."):
            data, filename = export_error_patterns(format=export_format.lower())

            if data and filename:
                st.download_button(
                    label=f"⬇️ Download {filename}",
                    data=data,
                    file_name=filename,
                    mime="text/csv" if export_format == "CSV" else "application/json",
                    use_container_width=True
                )
                st.success(f"✅ {filename} ready for download!")

    st.markdown("---")

    # Section 4: Vote Results Summary
    st.subheader("📊 Vote Results Summary")
    st.markdown("Current vote tallies by law.")

    if st.button("📥 Export Vote Results", use_container_width=True):
        with st.spinner(f"Exporting vote results to {export_format}..."):
            data, filename = export_vote_results(format=export_format.lower())

            if data and filename:
                st.download_button(
                    label=f"⬇️ Download {filename}",
                    data=data,
                    file_name=filename,
                    mime="text/csv" if export_format == "CSV" else "application/json",
                    use_container_width=True
                )
                st.success(f"✅ {filename} ready for download!")

    st.markdown("---")

    # Export All
    st.subheader("📦 Export All Data")
    st.markdown("Export all audit data in one action.")

    if st.button("📥 Export All Audit Data", type="primary", use_container_width=True):
        with st.spinner("Exporting all audit data..."):
            exports = []

            # Export each type
            data, filename = export_vote_audit(format=export_format.lower())
            if data and filename:
                exports.append((data, filename))

            data, filename = export_duplicate_stats(format=export_format.lower())
            if data and filename:
                exports.append((data, filename))

            data, filename = export_error_patterns(format=export_format.lower())
            if data and filename:
                exports.append((data, filename))

            data, filename = export_vote_results(format=export_format.lower())
            if data and filename:
                exports.append((data, filename))

            # Display download buttons
            if exports:
                st.success(f"✅ All exports ready! ({len(exports)} files)")
                for data, filename in exports:
                    st.download_button(
                        label=f"⬇️ Download {filename}",
                        data=data,
                        file_name=filename,
                        mime="text/csv" if export_format == "CSV" else "application/json",
                        key=f"download_{filename}"
                    )

# Tab 7: Admin Panel - Election System Management
with tab7:
    st.header("⚙️ Election Admin Panel")
    st.info("🔒 **TESTING MODE**: This admin panel is for setting up elections. After testing, use secured access for production.")

    # Sub-tabs for different admin functions
    admin_tab1, admin_tab2, admin_tab3, admin_tab4 = st.tabs([
        "🗳️  Elections",
        "📍 Regions",
        "🎨 Political Parties",
        "👥 Candidates"
    ])

    # === Elections Management ===
    with admin_tab1:
        st.subheader("Elections Management")

        col1, col2 = st.columns([2, 1])

        with col1:
            elections_df = get_all_elections()
            if not elections_df.empty:
                st.dataframe(elections_df, use_container_width=True)
            else:
                st.info("No elections yet")

        with col2:
            st.subheader("Add New Election")

            new_election_code = st.text_input("Election Code", placeholder="PROV-2029", key="new_election_code")
            new_election_name = st.text_input("Election Name", placeholder="Élection provinciale 2029", key="new_election_name")
            new_election_type = st.selectbox("Type", ["provincial", "municipal", "federal", "referendum"], key="new_election_type")
            new_election_date = st.date_input("Election Date", key="new_election_date")

            st.markdown("---")
            st.markdown("**🗳️ Voting Method**")
            new_voting_method = st.radio(
                "Select voting method",
                ["single_choice", "ranked_choice"],
                format_func=lambda x: "📊 Single Choice (Current System)" if x == "single_choice" else "✅ Ranked-Choice Voting (Electoral Reform)",
                key="new_voting_method",
                help="Ranked-choice voting allows voters to rank candidates by preference (1st, 2nd, 3rd, etc.)"
            )

            if new_voting_method == "ranked_choice":
                st.info("✅ **Ranked-Choice Voting Enabled** - Voters can rank candidates in order of preference. If no candidate wins >50%, votes are redistributed using instant-runoff.")

            st.markdown("---")
            st.markdown("**⏰ Voting Period**")
            col_start, col_end = st.columns(2)
            with col_start:
                new_start_date = st.date_input("Start Date", key="new_start_date")
                new_start_time = st.time_input("Start Time", value=datetime.strptime("08:00", "%H:%M").time(), key="new_start_time")
            with col_end:
                new_end_date = st.date_input("End Date", key="new_end_date")
                new_end_time = st.time_input("End Time", value=datetime.strptime("20:00", "%H:%M").time(), key="new_end_time")

            # Combine date and time
            from datetime import datetime as dt, timezone
            new_start_datetime = dt.combine(new_start_date, new_start_time).replace(tzinfo=timezone.utc) if new_start_date and new_start_time else None
            new_end_datetime = dt.combine(new_end_date, new_end_time).replace(tzinfo=timezone.utc) if new_end_date and new_end_time else None

            if st.button("➕ Add Election", use_container_width=True, type="primary"):
                if new_election_code and new_election_name:
                    if new_start_datetime and new_end_datetime and new_end_datetime <= new_start_datetime:
                        st.error("❌ End datetime must be after start datetime!")
                    else:
                        success, message = add_election(
                            new_election_code,
                            new_election_name,
                            new_election_type,
                            new_election_date,
                            new_start_datetime,
                            new_end_datetime,
                            new_voting_method
                        )
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
                else:
                    st.warning("Please fill all required fields")

    # === Regions Management ===
    with admin_tab2:
        st.subheader("Regions Management (Electoral Districts)")

        col1, col2 = st.columns([2, 1])

        with col1:
            regions_df = get_all_regions()
            if not regions_df.empty:
                st.dataframe(regions_df, use_container_width=True)
            else:
                st.info("No regions yet")

        with col2:
            st.subheader("Add New Region")

            new_region_code = st.text_input("Region Code", placeholder="MONTREAL-SUD", key="new_region_code", help="Example: ABITIBI-OUEST, MONTREAL-CENTRE")
            new_region_name = st.text_input("Region Name", placeholder="Montréal-Sud", key="new_region_name", help="Example: Abitibi-Ouest, Montréal-Centre")
            new_region_desc = st.text_area("Description (optional)", key="new_region_desc")

            if st.button("➕ Add Region", use_container_width=True):
                if new_region_code and new_region_name:
                    success, message = add_region(new_region_code, new_region_name, new_region_desc)
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
                else:
                    st.warning("Please fill all required fields")

    # === Political Parties Management ===
    with admin_tab3:
        st.subheader("Political Parties Management")

        col1, col2 = st.columns([2, 1])

        with col1:
            parties_df = get_all_parties()
            if not parties_df.empty:
                # Add color visualization
                def color_box(color):
                    return f'<div style="width:30px; height:20px; background-color:{color}; border:1px solid #ccc;"></div>'

                st.dataframe(parties_df, use_container_width=True)
            else:
                st.info("No political parties yet")

        with col2:
            st.subheader("Add New Party")

            new_party_code = st.text_input("Party Code", placeholder="NPD", key="new_party_code", max_chars=10, help="Example: CAQ, PLQ, PQ, QS")
            new_party_name = st.text_input("Party Name", placeholder="Nouveau Parti Démocratique", key="new_party_name", help="Full party name")
            new_party_color = st.color_picker("Party Color", value="#808080", key="new_party_color", help="Choose party color for UI")

            if st.button("➕ Add Party", use_container_width=True):
                if new_party_code and new_party_name:
                    success, message = add_party(new_party_code, new_party_name, new_party_color)
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
                else:
                    st.warning("Please fill all required fields")

    # === Candidates Management ===
    with admin_tab4:
        st.subheader("Candidates Management (Organized by Region & Party)")

        elections_df = get_all_elections()

        if elections_df.empty:
            st.warning("⚠️ No elections created yet. Create an election first.")
        else:
            # Select election
            selected_election = st.selectbox(
                "Select Election",
                options=elections_df['ID'].tolist(),
                format_func=lambda x: f"{elections_df[elections_df['ID']==x]['Name'].values[0]} ({elections_df[elections_df['ID']==x]['Code'].values[0]})"
            )

            st.markdown("---")

            col1, col2 = st.columns([2, 1])

            with col1:
                st.subheader("Current Candidates")
                candidates_df = get_candidates_by_election(selected_election)

                if not candidates_df.empty:
                    # Group by region
                    for region in candidates_df['Region'].unique():
                        st.markdown(f"**📍 {region}**")
                        region_candidates = candidates_df[candidates_df['Region'] == region]

                        # Display candidates by party
                        for _, row in region_candidates.iterrows():
                            party_badge = f"<span style='background-color:#e0e0e0; padding:2px 8px; border-radius:3px; margin-right:8px;'>{row['Party Code']}</span>"
                            st.markdown(f"{party_badge} **{row['First Name']} {row['Last Name']}** - {row['Party']}", unsafe_allow_html=True)

                        st.markdown("")
                else:
                    st.info("No candidates for this election yet")

            with col2:
                st.subheader("Add New Candidate")

                # Get regions and parties
                regions_df = get_all_regions()
                parties_df = get_all_parties()

                if regions_df.empty or parties_df.empty:
                    st.warning("⚠️ Please create regions and political parties first")
                else:
                    selected_region = st.selectbox(
                        "Region",
                        options=regions_df['ID'].tolist(),
                        format_func=lambda x: regions_df[regions_df['ID']==x]['Name'].values[0],
                        key="candidate_region"
                    )

                    selected_party = st.selectbox(
                        "Political Party",
                        options=parties_df['ID'].tolist(),
                        format_func=lambda x: f"{parties_df[parties_df['ID']==x]['Code'].values[0]} - {parties_df[parties_df['ID']==x]['Name'].values[0]}",
                        key="candidate_party"
                    )

                    candidate_first_name = st.text_input("First Name", placeholder="Gabrielle", key="candidate_first_name")
                    candidate_last_name = st.text_input("Last Name", placeholder="Savois", key="candidate_last_name")

                    st.info(f"**Example**: Region: {regions_df[regions_df['ID']==selected_region]['Name'].values[0]}, Party: {parties_df[parties_df['ID']==selected_party]['Code'].values[0]}")

                    if st.button("➕ Add Candidate", type="primary", use_container_width=True):
                        if candidate_first_name and candidate_last_name:
                            success, message = add_candidate(
                                selected_election,
                                selected_region,
                                selected_party,
                                candidate_first_name,
                                candidate_last_name
                            )
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)
                        else:
                            st.warning("Please fill all required fields")

# Footer
st.markdown("---")
st.caption("Voting System Test GUI v3.0 | Admin Panel Added | Election Management Ready")
