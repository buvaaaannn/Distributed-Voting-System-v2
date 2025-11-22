"""PostgreSQL database client for validation worker."""

import psycopg2
import psycopg2.pool
import psycopg2.extras
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from config import Config

logger = logging.getLogger(__name__)


class DatabaseClient:
    """PostgreSQL client for audit logging."""

    def __init__(self):
        """Initialize PostgreSQL connection pool."""
        try:
            self.pool = psycopg2.pool.ThreadedConnectionPool(
                Config.POSTGRES_MIN_POOL_SIZE,
                Config.POSTGRES_MAX_POOL_SIZE,
                Config.get_postgres_dsn()
            )
            logger.info("PostgreSQL connection pool created successfully")
            self._test_connection()
        except psycopg2.Error as e:
            logger.error(f"Failed to create PostgreSQL connection pool: {e}")
            raise

    def _test_connection(self):
        """Test database connection on initialization."""
        conn = None
        try:
            conn = self.pool.getconn()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            logger.info("PostgreSQL connection test successful")
        except psycopg2.Error as e:
            logger.error(f"PostgreSQL connection test failed: {e}")
            raise
        finally:
            if conn:
                self.pool.putconn(conn)

    def insert_audit_log(
        self,
        voter_hash: str,
        law_id: str,
        vote: str,
        status: str,
        vote_timestamp: datetime,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Insert audit log entry into vote_audit table.

        Args:
            voter_hash: The voter's hash
            law_id: The law ID voted on
            vote: The vote choice (oui/non)
            status: Vote status (valid, duplicate, invalid)
            vote_timestamp: When the vote was cast
            metadata: Additional metadata as JSON

        Returns:
            The inserted audit log ID
        """
        conn = None
        try:
            conn = self.pool.getconn()
            cursor = conn.cursor()

            query = """
                INSERT INTO vote_audit (
                    vote_hash,
                    law_id,
                    vote,
                    status,
                    timestamp,
                    processed_at,
                    metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """

            cursor.execute(
                query,
                (
                    voter_hash,
                    law_id,
                    vote,
                    status,
                    vote_timestamp,
                    datetime.utcnow(),
                    psycopg2.extras.Json(metadata) if metadata else None
                )
            )

            audit_id = cursor.fetchone()[0]
            conn.commit()
            cursor.close()

            logger.debug(f"Inserted audit log with ID {audit_id} for hash {voter_hash}")
            return audit_id

        except psycopg2.Error as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error inserting audit log: {e}")
            raise
        finally:
            if conn:
                self.pool.putconn(conn)

    def insert_vote_record(
        self,
        voter_hash: str,
        candidate_id: int,
        vote_timestamp: datetime,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Insert valid vote record into votes table.

        Args:
            voter_hash: The voter's hash
            candidate_id: The candidate ID voted for
            vote_timestamp: When the vote was cast
            metadata: Additional metadata as JSON

        Returns:
            The inserted vote ID
        """
        conn = None
        try:
            conn = self.pool.getconn()
            cursor = conn.cursor()

            query = """
                INSERT INTO votes (
                    voter_hash,
                    candidate_id,
                    vote_timestamp,
                    metadata
                ) VALUES (%s, %s, %s, %s)
                RETURNING id
            """

            cursor.execute(
                query,
                (
                    voter_hash,
                    candidate_id,
                    vote_timestamp,
                    psycopg2.extras.Json(metadata) if metadata else None
                )
            )

            vote_id = cursor.fetchone()[0]
            conn.commit()
            cursor.close()

            logger.debug(f"Inserted vote record with ID {vote_id} for hash {voter_hash}")
            return vote_id

        except psycopg2.Error as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error inserting vote record: {e}")
            raise
        finally:
            if conn:
                self.pool.putconn(conn)

    def health_check(self) -> bool:
        """
        Check database health.

        Returns:
            True if database is healthy, False otherwise
        """
        conn = None
        try:
            conn = self.pool.getconn()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return True
        except psycopg2.Error as e:
            logger.error(f"Database health check failed: {e}")
            return False
        finally:
            if conn:
                self.pool.putconn(conn)

    def close(self):
        """Close all database connections."""
        try:
            self.pool.closeall()
            logger.info("PostgreSQL connection pool closed")
        except Exception as e:
            logger.error(f"Error closing database connections: {e}")
