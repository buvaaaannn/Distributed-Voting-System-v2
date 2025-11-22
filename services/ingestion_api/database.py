"""PostgreSQL database connection and queries."""
import asyncpg
from typing import Optional, Dict
from datetime import datetime
import logging

from config import settings

logger = logging.getLogger(__name__)


class Database:
    """Async PostgreSQL database manager."""

    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def initialize(self):
        """Initialize database connection pool."""
        try:
            self.pool = await asyncpg.create_pool(
                settings.postgres_dsn,
                min_size=settings.POSTGRES_POOL_MIN_SIZE,
                max_size=settings.POSTGRES_POOL_MAX_SIZE,
                command_timeout=60
            )
            logger.info("PostgreSQL connection pool initialized successfully")

            # Verify connection
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
                logger.info("PostgreSQL connection verified")

        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL connection pool: {e}")
            raise

    async def get_results(self, law_id: str) -> Optional[Dict]:
        """
        Get vote results for a specific law.

        Args:
            law_id: Law identifier

        Returns:
            Dictionary with vote counts or None if not found
        """
        try:
            async with self.pool.acquire() as conn:
                # Query aggregated results from vote_results table
                query = """
                    SELECT
                        law_id,
                        oui_count,
                        non_count,
                        total_votes,
                        updated_at
                    FROM vote_results
                    WHERE law_id = $1
                """

                row = await conn.fetchrow(query, law_id)

                if row:
                    return {
                        "law_id": row["law_id"],
                        "oui_count": row["oui_count"],
                        "non_count": row["non_count"],
                        "total_votes": row["total_votes"],
                        "updated_at": row["updated_at"]
                    }

                # If no results found, check if law exists with zero votes
                exists_query = "SELECT 1 FROM laws WHERE law_id = $1"
                exists = await conn.fetchval(exists_query, law_id)

                if exists:
                    # Law exists but no votes yet
                    return {
                        "law_id": law_id,
                        "oui_count": 0,
                        "non_count": 0,
                        "total_votes": 0,
                        "updated_at": datetime.utcnow()
                    }

                # Law doesn't exist
                return None

        except Exception as e:
            logger.error(f"Error getting results for law_id {law_id}: {e}")
            raise

    async def get_all_results(self) -> list:
        """
        Get vote results for all laws.

        Returns:
            List of dictionaries with vote counts
        """
        try:
            async with self.pool.acquire() as conn:
                query = """
                    SELECT
                        law_id,
                        oui_count,
                        non_count,
                        total_votes,
                        updated_at
                    FROM vote_results
                    ORDER BY law_id
                """

                rows = await conn.fetch(query)

                return [
                    {
                        "law_id": row["law_id"],
                        "oui_count": row["oui_count"],
                        "non_count": row["non_count"],
                        "total_votes": row["total_votes"],
                        "updated_at": row["updated_at"]
                    }
                    for row in rows
                ]

        except Exception as e:
            logger.error(f"Error getting all results: {e}")
            raise

    async def check_health(self) -> bool:
        """
        Check PostgreSQL connection health.

        Returns:
            bool: True if healthy, False otherwise
        """
        try:
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
                return True
        except Exception as e:
            logger.error(f"PostgreSQL health check failed: {e}")
            return False

    async def close(self):
        """Close database connection pool."""
        try:
            if self.pool:
                await self.pool.close()
                logger.info("PostgreSQL connection pool closed successfully")
        except Exception as e:
            logger.error(f"Error closing PostgreSQL connection pool: {e}")

    # Election Voting Methods

    async def get_elections(self) -> list:
        """Get all active elections."""
        try:
            async with self.pool.acquire() as conn:
                query = """
                    SELECT id, election_code, election_name, election_type,
                           election_date, status
                    FROM elections
                    WHERE status IN ('draft', 'active')
                    ORDER BY election_date DESC, id DESC
                """
                rows = await conn.fetch(query)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting elections: {e}")
            raise

    async def get_regions(self) -> list:
        """Get all regions."""
        try:
            async with self.pool.acquire() as conn:
                query = """
                    SELECT id, region_code, region_name, description
                    FROM regions
                    ORDER BY region_name
                """
                rows = await conn.fetch(query)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting regions: {e}")
            raise

    async def get_candidates(self, election_id: int, region_id: int) -> list:
        """Get candidates for a specific election and region."""
        try:
            async with self.pool.acquire() as conn:
                query = """
                    SELECT
                        c.id, c.first_name, c.last_name,
                        p.party_code, p.party_name, p.party_color,
                        c.bio, c.photo_url
                    FROM candidates c
                    JOIN political_parties p ON c.party_id = p.id
                    WHERE c.election_id = $1 AND c.region_id = $2
                          AND c.status = 'active'
                    ORDER BY p.party_name
                """
                rows = await conn.fetch(query, election_id, region_id)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting candidates: {e}")
            raise

    async def submit_election_vote(self, vote_hash: str, election_id: int,
                                   region_id: int, candidate_id: int,
                                   metadata: dict) -> bool:
        """
        Submit an election vote directly to database.
        Returns True if successful, False if duplicate.
        """
        try:
            async with self.pool.acquire() as conn:
                # Start transaction
                async with conn.transaction():
                    # Insert vote
                    insert_query = """
                        INSERT INTO election_votes
                        (vote_hash, election_id, region_id, candidate_id,
                         vote_timestamp, processed_at, metadata)
                        VALUES ($1, $2, $3, $4, NOW(), NOW(), $5)
                        RETURNING id
                    """
                    import json
                    vote_id = await conn.fetchval(
                        insert_query,
                        vote_hash, election_id, region_id, candidate_id,
                        json.dumps(metadata)
                    )

                    # Update results
                    update_query = """
                        INSERT INTO election_results
                        (election_id, region_id, candidate_id, vote_count, percentage)
                        VALUES ($1, $2, $3, 1, 0.00)
                        ON CONFLICT (election_id, region_id, candidate_id)
                        DO UPDATE SET
                            vote_count = election_results.vote_count + 1,
                            updated_at = NOW()
                    """
                    await conn.execute(update_query, election_id, region_id, candidate_id)

                    return True

        except Exception as e:
            logger.error(f"Error submitting election vote: {e}")
            return False

    async def get_election_results(self, election_id: int, region_id: int) -> Optional[Dict]:
        """Get election results for a specific region."""
        try:
            async with self.pool.acquire() as conn:
                query = """
                    SELECT
                        r.region_name,
                        c.id as candidate_id,
                        c.first_name || ' ' || c.last_name as candidate_name,
                        p.party_code, p.party_name, p.party_color,
                        COALESCE(er.vote_count, 0) as votes,
                        COALESCE(er.updated_at, NOW()) as updated_at
                    FROM candidates c
                    JOIN political_parties p ON c.party_id = p.id
                    JOIN regions r ON c.region_id = r.id
                    LEFT JOIN election_results er ON c.id = er.candidate_id
                        AND er.election_id = c.election_id
                        AND er.region_id = c.region_id
                    WHERE c.election_id = $1 AND c.region_id = $2
                    ORDER BY votes DESC, p.party_code
                """
                rows = await conn.fetch(query, election_id, region_id)

                if not rows:
                    return None

                total_votes = sum(row['votes'] for row in rows)
                candidates = []
                for row in rows:
                    percentage = (row['votes'] / total_votes * 100) if total_votes > 0 else 0
                    candidates.append({
                        'candidate_id': row['candidate_id'],
                        'name': row['candidate_name'],
                        'party_code': row['party_code'],
                        'party_name': row['party_name'],
                        'party_color': row['party_color'],
                        'votes': row['votes'],
                        'percentage': round(percentage, 2)
                    })

                return {
                    'election_id': election_id,
                    'region_id': region_id,
                    'region_name': rows[0]['region_name'],
                    'candidates': candidates,
                    'total_votes': total_votes,
                    'updated_at': rows[0]['updated_at']
                }

        except Exception as e:
            logger.error(f"Error getting election results: {e}")
            raise

    async def get_election_timing(self, election_id: int) -> Optional[tuple]:
        """
        Get election start and end datetime.
        Returns (start_datetime, end_datetime) or None if election not found.
        """
        try:
            async with self.pool.acquire() as conn:
                query = """
                    SELECT start_datetime, end_datetime
                    FROM elections
                    WHERE id = $1
                """
                row = await conn.fetchrow(query, election_id)
                if row:
                    return (row['start_datetime'], row['end_datetime'])
                return None
        except Exception as e:
            logger.error(f"Error getting election timing: {e}")
            return None

    async def check_health(self) -> bool:
        """Check database connection health."""
        try:
            if not self.pool:
                return False
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
                return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False


# Global database instance
database = Database()
