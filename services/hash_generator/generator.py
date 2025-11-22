#!/usr/bin/env python3
"""
Hash Generator for Distributed Voting System
Generates cryptographic hashes for voter authentication
"""

import argparse
import hashlib
import json
import os
import random
import string
from pathlib import Path
from typing import Dict, List

try:
    from tqdm import tqdm
except ImportError:
    # Fallback if tqdm is not available
    def tqdm(iterable, **kwargs):
        return iterable


def generate_nas() -> str:
    """Generate a random 9-digit NAS (digits only, no prefix)"""
    return ''.join(random.choices(string.digits, k=9))


def generate_code() -> str:
    """Generate a random 6-character code (uppercase alphanumeric)"""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=6))


def generate_vote() -> str:
    """Generate a random vote (oui or non)"""
    return random.choice(['oui', 'non'])


def create_hash(nas: str, code: str, law_id: str) -> str:
    """
    Create SHA-256 hash from NAS, code, and law ID
    Format: sha256(f"{nas}|{code.upper()}|{law_id}")
    """
    hash_input = f"{nas}|{code.upper()}|{law_id}"
    return hashlib.sha256(hash_input.encode()).hexdigest()


def generate_hash_entry(law_id: str) -> Dict[str, str]:
    """Generate a single hash entry with all required fields"""
    nas = generate_nas()
    code = generate_code()
    vote = generate_vote()
    hash_value = create_hash(nas, code, law_id)

    return {
        "nas": nas,
        "code": code,
        "law_id": law_id,
        "hash": hash_value,
        "vote": vote
    }


def save_shard(entries: List[Dict[str, str]], output_dir: Path, shard_index: int) -> str:
    """Save a shard of hash entries to a JSON file"""
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = output_dir / f"hashes_shard_{shard_index:04d}.json"

    with open(filename, 'w') as f:
        json.dump(entries, f, indent=2)

    return str(filename)


def generate_hashes(count: int, output_dir: str, law_id: str, shard_size: int = 1_000_000):
    """
    Generate hash entries and save them to sharded JSON files

    Args:
        count: Total number of hashes to generate
        output_dir: Directory to save output files
        law_id: Law identifier (e.g., L2025-001)
        shard_size: Number of hashes per shard file (default: 1M)
    """
    output_path = Path(output_dir)
    current_shard = []
    shard_index = 0
    saved_files = []

    # Statistics
    vote_stats = {'oui': 0, 'non': 0}

    print(f"Generating {count:,} hashes for law {law_id}...")
    print(f"Output directory: {output_path.absolute()}")
    print(f"Shard size: {shard_size:,} hashes per file\n")

    for i in tqdm(range(count), desc="Generating hashes", unit="hash"):
        entry = generate_hash_entry(law_id)
        current_shard.append(entry)
        vote_stats[entry['vote']] += 1

        # Save shard when it reaches the size limit
        if len(current_shard) >= shard_size:
            filename = save_shard(current_shard, output_path, shard_index)
            saved_files.append(filename)
            current_shard = []
            shard_index += 1

    # Save remaining entries in the last shard
    if current_shard:
        filename = save_shard(current_shard, output_path, shard_index)
        saved_files.append(filename)

    # Print summary statistics
    print("\n" + "="*60)
    print("GENERATION COMPLETE")
    print("="*60)
    print(f"Total hashes generated: {count:,}")
    print(f"Law ID: {law_id}")
    print(f"Output directory: {output_path.absolute()}")
    print(f"\nVote distribution:")
    print(f"  - Oui: {vote_stats['oui']:,} ({vote_stats['oui']/count*100:.2f}%)")
    print(f"  - Non: {vote_stats['non']:,} ({vote_stats['non']/count*100:.2f}%)")
    print(f"\nFiles created: {len(saved_files)}")
    for i, filename in enumerate(saved_files):
        file_size = os.path.getsize(filename) / (1024 * 1024)  # Size in MB
        print(f"  {i+1}. {Path(filename).name} ({file_size:.2f} MB)")

    total_size = sum(os.path.getsize(f) for f in saved_files) / (1024 * 1024)
    print(f"\nTotal size: {total_size:.2f} MB")
    print("="*60)


def main():
    """Main entry point for the hash generator"""
    parser = argparse.ArgumentParser(
        description='Generate cryptographic hashes for distributed voting system',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate 1 million hashes
  python generator.py --count 1000000 --output ./output

  # Generate 5 million hashes for a specific law
  python generator.py --count 5000000 --output ./output --law-id L2025-042

  # Generate 100 hashes for testing
  python generator.py --count 100 --output ./test_output
        """
    )

    parser.add_argument(
        '--count',
        type=int,
        required=True,
        help='Number of hashes to generate'
    )

    parser.add_argument(
        '--output',
        type=str,
        required=True,
        help='Output directory for hash files'
    )

    parser.add_argument(
        '--law-id',
        type=str,
        default='L2025-001',
        help='Law identifier (default: L2025-001)'
    )

    parser.add_argument(
        '--shard-size',
        type=int,
        default=1_000_000,
        help='Number of hashes per shard file (default: 1,000,000)'
    )

    args = parser.parse_args()

    # Validate arguments
    if args.count <= 0:
        parser.error("Count must be a positive number")

    if args.shard_size <= 0:
        parser.error("Shard size must be a positive number")

    # Generate hashes
    generate_hashes(
        count=args.count,
        output_dir=args.output,
        law_id=args.law_id,
        shard_size=args.shard_size
    )


if __name__ == '__main__':
    main()
