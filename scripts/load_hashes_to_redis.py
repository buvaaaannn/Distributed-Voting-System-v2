#!/usr/bin/env python3
"""
Load pre-generated voter hashes into Redis.

This script reads sharded hash files from data/hashes/ and loads them into Redis
using the 'valid_hashes' SET. It's designed to handle large datasets efficiently
by batching SADD operations.

Usage:
    python load_hashes_to_redis.py [--redis-host HOST] [--redis-port PORT] [--batch-size SIZE]

Environment Variables:
    REDIS_HOST: Redis server host (default: localhost)
    REDIS_PORT: Redis server port (default: 6379)
    REDIS_PASSWORD: Redis password (optional)
"""

import os
import sys
import json
import argparse
import redis
from pathlib import Path
from typing import List, Generator
from tqdm import tqdm


class HashLoader:
    """Load voter hashes into Redis efficiently."""

    def __init__(
        self,
        redis_host: str = 'localhost',
        redis_port: int = 6379,
        redis_password: str = None,
        redis_db: int = 0,
        batch_size: int = 10000
    ):
        """
        Initialize HashLoader.

        Args:
            redis_host: Redis server hostname
            redis_port: Redis server port
            redis_password: Redis password (optional)
            redis_db: Redis database number
            batch_size: Number of hashes to batch per SADD operation
        """
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_password = redis_password
        self.redis_db = redis_db
        self.batch_size = batch_size
        self.redis_client = None

    def connect(self) -> bool:
        """
        Connect to Redis.

        Returns:
            bool: True if connection successful
        """
        try:
            self.redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                password=self.redis_password,
                db=self.redis_db,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            self.redis_client.ping()
            print(f"✓ Connected to Redis at {self.redis_host}:{self.redis_port}")
            return True
        except redis.ConnectionError as e:
            print(f"✗ Failed to connect to Redis: {e}", file=sys.stderr)
            return False
        except Exception as e:
            print(f"✗ Unexpected error connecting to Redis: {e}", file=sys.stderr)
            return False

    def read_hash_files(self, hash_dir: Path) -> Generator[str, None, None]:
        """
        Read all hash files from directory.

        Args:
            hash_dir: Directory containing hash files

        Yields:
            str: Individual hash
        """
        if not hash_dir.exists():
            print(f"✗ Hash directory does not exist: {hash_dir}", file=sys.stderr)
            return

        # Find all hash files (JSON or TXT)
        hash_files = list(hash_dir.glob('*.json')) + list(hash_dir.glob('*.txt'))

        if not hash_files:
            print(f"✗ No hash files found in {hash_dir}", file=sys.stderr)
            return

        print(f"Found {len(hash_files)} hash file(s)")

        for file_path in sorted(hash_files):
            print(f"Reading: {file_path.name}")

            try:
                if file_path.suffix == '.json':
                    # JSON format: {"hashes": ["hash1", "hash2", ...]}
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                        if isinstance(data, list): # If it's a list directly
                            hashes = data
                        elif isinstance(data, dict) and 'hashes' in data: # If it's the expected dict format
                            hashes = data['hashes']
                        else:
                            print(f"✗ Unexpected JSON format in {file_path}: Expected a list or a dict with 'hashes' key.", file=sys.stderr)
                            continue # Skip this file

                        for entry_dict in hashes:
                            if isinstance(entry_dict, dict) and 'hash' in entry_dict:
                                yield entry_dict['hash']
                            else:
                                print(f"✗ Unexpected entry format in {file_path}: Expected a dictionary with 'hash' key.", file=sys.stderr)
                else:
                    # Text format: one hash per line
                    with open(file_path, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#'):
                                yield line
            except json.JSONDecodeError as e:
                print(f"✗ Error parsing JSON file {file_path}: {e}", file=sys.stderr)
            except Exception as e:
                print(f"✗ Error reading file {file_path}: {e}", file=sys.stderr)

    def count_total_hashes(self, hash_dir: Path) -> int:
        """
        Count total number of hashes in all files.

        Args:
            hash_dir: Directory containing hash files

        Returns:
            int: Total count
        """
        total = 0
        hash_files = list(hash_dir.glob('*.json')) + list(hash_dir.glob('*.txt'))

        for file_path in hash_files:
            try:
                if file_path.suffix == '.json':
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            total += len(data)
                        elif isinstance(data, dict) and 'hashes' in data:
                            total += len(data['hashes'])
                        # else: ignore malformed files for counting, error will be caught during loading
                else:
                    with open(file_path, 'r') as f:
                        total += sum(1 for line in f if line.strip() and not line.startswith('#'))
            except Exception:
                pass

        return total

    def load_hashes(self, hash_dir: Path, clear_existing: bool = False) -> dict:
        """
        Load all hashes into Redis.

        Args:
            hash_dir: Directory containing hash files
            clear_existing: If True, clear existing hashes before loading

        Returns:
            dict: Statistics about the load operation
        """
        if not self.redis_client:
            raise RuntimeError("Not connected to Redis. Call connect() first.")

        stats = {
            'total_hashes': 0,
            'loaded_hashes': 0,
            'duplicate_hashes': 0,
            'errors': 0
        }

        # Clear existing hashes if requested
        if clear_existing:
            print("Clearing existing hashes...")
            self.redis_client.delete('valid_hashes')

        # Count total for progress bar
        total_hashes = self.count_total_hashes(hash_dir)
        print(f"Total hashes to load: {total_hashes:,}")

        # Load hashes in batches
        batch = []
        pipeline = self.redis_client.pipeline()

        with tqdm(total=total_hashes, desc="Loading hashes", unit="hashes") as pbar:
            for hash_value in self.read_hash_files(hash_dir):
                stats['total_hashes'] += 1
                batch.append(hash_value)

                # Process batch when it reaches batch_size
                if len(batch) >= self.batch_size:
                    try:
                        # Use pipeline for efficiency
                        pipeline.sadd('valid_hashes', *batch)
                        pipeline.execute()
                        stats['loaded_hashes'] += len(batch)
                        pbar.update(len(batch))
                        batch = []
                    except Exception as e:
                        print(f"\n✗ Error loading batch: {e}", file=sys.stderr)
                        stats['errors'] += len(batch)
                        batch = []

            # Load remaining hashes
            if batch:
                try:
                    pipeline.sadd('valid_hashes', *batch)
                    pipeline.execute()
                    stats['loaded_hashes'] += len(batch)
                    pbar.update(len(batch))
                except Exception as e:
                    print(f"\n✗ Error loading final batch: {e}", file=sys.stderr)
                    stats['errors'] += len(batch)

        # Verify count in Redis
        redis_count = self.redis_client.scard('valid_hashes')
        stats['duplicate_hashes'] = stats['loaded_hashes'] - redis_count

        print(f"\n✓ Load complete!")
        print(f"  Total hashes processed: {stats['total_hashes']:,}")
        print(f"  Unique hashes in Redis: {redis_count:,}")
        print(f"  Duplicates detected: {stats['duplicate_hashes']:,}")
        if stats['errors'] > 0:
            print(f"  Errors: {stats['errors']:,}")

        return stats

    def verify_sample(self, sample_hashes: List[str]) -> dict:
        """
        Verify that sample hashes exist in Redis.

        Args:
            sample_hashes: List of hashes to check

        Returns:
            dict: Verification results
        """
        if not self.redis_client:
            raise RuntimeError("Not connected to Redis. Call connect() first.")

        results = {
            'total': len(sample_hashes),
            'found': 0,
            'missing': 0
        }

        for hash_value in sample_hashes:
            if self.redis_client.sismember('valid_hashes', hash_value):
                results['found'] += 1
            else:
                results['missing'] += 1

        return results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Load pre-generated voter hashes into Redis'
    )
    parser.add_argument(
        '--redis-host',
        default=os.getenv('REDIS_HOST', 'localhost'),
        help='Redis server host (default: localhost)'
    )
    parser.add_argument(
        '--redis-port',
        type=int,
        default=int(os.getenv('REDIS_PORT', 6379)),
        help='Redis server port (default: 6379)'
    )
    parser.add_argument(
        '--redis-password',
        default=os.getenv('REDIS_PASSWORD'),
        help='Redis password (optional)'
    )
    parser.add_argument(
        '--redis-db',
        type=int,
        default=int(os.getenv('REDIS_DB', 0)),
        help='Redis database number (default: 0)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=10000,
        help='Batch size for SADD operations (default: 10000)'
    )
    parser.add_argument(
        '--hash-dir',
        type=Path,
        default=Path(__file__).parent.parent / 'data' / 'hashes',
        help='Directory containing hash files (default: ../data/hashes)'
    )
    parser.add_argument(
        '--clear',
        action='store_true',
        help='Clear existing hashes before loading'
    )

    args = parser.parse_args()

    # Initialize loader
    loader = HashLoader(
        redis_host=args.redis_host,
        redis_port=args.redis_port,
        redis_password=args.redis_password,
        redis_db=args.redis_db,
        batch_size=args.batch_size
    )

    # Connect to Redis
    if not loader.connect():
        sys.exit(1)

    # Load hashes
    try:
        stats = loader.load_hashes(args.hash_dir, clear_existing=args.clear)

        # Exit with error code if there were errors
        if stats['errors'] > 0:
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n✗ Load interrupted by user", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Fatal error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
