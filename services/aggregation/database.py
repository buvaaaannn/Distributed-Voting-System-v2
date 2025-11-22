"""
PostgreSQL database operations for vote aggregation.
"""
import logging
import time
from typing import List, Dict, Tuple
from contextlib import contextmanager
import psycopg2
from psycopg2 import pool, sql, errors
from psycopg2.extras import execute_batch

from config import config

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Custom exception for database errors."""
    pass


class Database:
    """PostgreSQL database connection and operations."""

    def __init__(self):
        """Initialize database connection pool."""
        self.connection_pool = None
        self._init_connection_pool()

    def _init_connection_pool(self):
        """Create database connection pool."""
        try:
            self.connection_pool = psycopg2.pool.ThreadedConnectionPool(
                config.POSTGRES_MIN_CONNECTIONS,
                config.POSTGRES_MAX_CONNECTIONS,
                host=config.POSTGRES_HOST,
                port=config.POSTGRES_PORT,
                database=config.POSTGRES_DB,
                user=config.POSTGRES_USER,
                password=config.POSTGRES_PASSWORD,
                connect_timeout=10
            )
            logger.info(
                f"Database connection pool created: "
                f"{config.POSTGRES_HOST}:{config.POSTGRES_PORT}/{config.POSTGRES_DB}"
            )
        except Exception as e:
            logger.error(f"Failed to create connection pool: {e}")
            raise DatabaseError(f"Connection pool creation failed: {e}")

    @contextmanager
    def get_connection(self):
        """
        Context manager for database connections.

        Yields:
            Connection object from the pool.
        """
        connection = None
        try:
            connection = self.connection_pool.getconn()
            yield connection
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            if connection:
                self.connection_pool.putconn(connection)

    def batch_update_results(self, votes: List[Dict]) -> Tuple[int, int]:
        """
        Batch update vote results in PostgreSQL.

        Args:
            votes: List of vote dictionaries with 'law_id' and 'choice' fields.

        Returns:
            Tuple of (success_count, failure_count)

        Raises:
            DatabaseError: If the batch update fails.
        """
        if not votes:
            return 0, 0

        # Aggregate votes by law_id and vote choice
        vote_aggregates = {}
        for vote in votes:
            law_id = vote.get('law_id')
            vote_choice = vote.get('vote', '').lower()  # Changed from 'choice' to 'vote'

            if law_id not in vote_aggregates:
                vote_aggregates[law_id] = {'oui': 0, 'non': 0}

            if vote_choice == 'oui':
                vote_aggregates[law_id]['oui'] += 1
            elif vote_choice == 'non':
                vote_aggregates[law_id]['non'] += 1
            else:
                logger.warning(f"Invalid vote choice '{vote_choice}' for law_id {law_id}")

        # Prepare batch update data with total_votes
        batch_data = [
            (law_id, counts['oui'], counts['non'], counts['oui'] + counts['non'])
            for law_id, counts in vote_aggregates.items()
        ]

        upsert_sql = """
        INSERT INTO vote_results (law_id, oui_count, non_count, total_votes, updated_at)
        VALUES (%s, %s, %s, %s, NOW())
        ON CONFLICT (law_id)
        DO UPDATE SET
            oui_count = vote_results.oui_count + EXCLUDED.oui_count,
            non_count = vote_results.non_count + EXCLUDED.non_count,
            total_votes = vote_results.total_votes + EXCLUDED.total_votes,
            updated_at = NOW()
        """

        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    execute_batch(cursor, upsert_sql, batch_data, page_size=100)
                conn.commit()

                success_count = len(votes)
                logger.info(
                    f"Batch update successful: {success_count} votes, "
                    f"{len(batch_data)} law_ids affected"
                )
                return success_count, 0

        except errors.UniqueViolation as e:
            logger.error(f"Unique constraint violation during batch update: {e}")
            raise DatabaseError(f"Duplicate key error: {e}")
        except errors.OperationalError as e:
            logger.error(f"Database operational error: {e}")
            raise DatabaseError(f"Operational error: {e}")
        except Exception as e:
            logger.error(f"Batch update failed: {e}")
            raise DatabaseError(f"Batch update error: {e}")

    def get_vote_counts(self, law_id: str) -> Tuple[int, int]:
        """
        Get current vote counts for a specific law.

        Args:
            law_id: The law identifier.

        Returns:
            Tuple of (oui_count, non_count)
        """
        query = """
        SELECT oui_count, non_count
        FROM vote_results
        WHERE law_id = %s
        """

        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, (law_id,))
                    result = cursor.fetchone()

                    if result:
                        return result[0], result[1]
                    else:
                        return 0, 0

        except Exception as e:
            logger.error(f"Failed to get vote counts for {law_id}: {e}")
            return 0, 0

    def get_all_vote_counts(self) -> Dict[str, Dict[str, int]]:
        """
        Get all vote counts from the database.

        Returns:
            Dictionary mapping law_id to {'oui': count, 'non': count}
        """
        query = """
        SELECT law_id, oui_count, non_count
        FROM vote_results
        """

        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query)
                    results = cursor.fetchall()

                    vote_counts = {}
                    for law_id, oui_count, non_count in results:
                        vote_counts[law_id] = {
                            'oui': oui_count,
                            'non': non_count
                        }

                    return vote_counts

        except Exception as e:
            logger.error(f"Failed to get all vote counts: {e}")
            return {}

    def close(self):
        """Close all connections in the pool."""
        if self.connection_pool:
            self.connection_pool.closeall()
            logger.info("Database connection pool closed")
