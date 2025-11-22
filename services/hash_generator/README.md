# Hash Generator Service

A containerized service for generating cryptographic hashes for the distributed voting system. This service creates unique authentication hashes for voters based on their NAS (National Authentication String), access code, and the law being voted on.

## Overview

The hash generator creates secure, unique identifiers for voter authentication in a distributed voting system. Each hash is generated from:

- **NAS**: 9-digit random number (digits only, no prefix)
- **Code**: 6-character random uppercase alphanumeric string
- **Law ID**: Identifier for the law being voted on (e.g., L2025-001)
- **Vote**: Random vote value (oui or non)

The hash is computed as: `SHA-256(f"{nas}|{code.upper()}|{law_id}")`

## Features

- Generates millions of hashes efficiently
- Sharded output (1 million hashes per file by default) for easy distribution
- Progress bar showing real-time generation status
- Comprehensive summary statistics
- Docker containerization for portability
- Configurable output and law ID

## Hash Format

Each generated entry contains:

```json
{
  "nas": "123456789",
  "code": "ABC123",
  "law_id": "L2025-001",
  "hash": "a1b2c3d4e5f6...",
  "vote": "oui"
}
```

The hash is computed using the exact format: `{nas_digits_only}|{code_uppercase}|{law_id}`

## Installation

### Local Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Make the script executable
chmod +x generator.py
```

### Docker Installation

```bash
# Build the Docker image
docker build -t hash-generator .
```

## Usage

### Local Usage

```bash
# Generate 1 million hashes
python generator.py --count 1000000 --output ./output

# Generate 5 million hashes for a specific law
python generator.py --count 5000000 --output ./output --law-id L2025-042

# Generate 100 hashes for testing
python generator.py --count 100 --output ./test_output

# Custom shard size (500k hashes per file)
python generator.py --count 2000000 --output ./output --shard-size 500000
```

### Docker Usage

```bash
# Generate 1 million hashes (output to mounted volume)
docker run -v $(pwd)/output:/output hash-generator \
  --count 1000000 \
  --output /output

# Generate hashes for a specific law
docker run -v $(pwd)/output:/output hash-generator \
  --count 5000000 \
  --output /output \
  --law-id L2025-042

# View help
docker run hash-generator --help
```

## Command-Line Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--count` | Yes | - | Number of hashes to generate |
| `--output` | Yes | - | Output directory for hash files |
| `--law-id` | No | L2025-001 | Law identifier |
| `--shard-size` | No | 1000000 | Number of hashes per shard file |

## Output Format

### File Naming

Generated files follow the pattern: `hashes_shard_NNNN.json`

Example:
- `hashes_shard_0000.json` - First million hashes
- `hashes_shard_0001.json` - Second million hashes
- `hashes_shard_0002.json` - Third million hashes

### File Structure

Each shard file contains a JSON array of hash entries:

```json
[
  {
    "nas": "847291635",
    "code": "X9K2L7",
    "law_id": "L2025-001",
    "hash": "7f3a8d9c2e1b4f6a5c8d9e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b",
    "vote": "oui"
  },
  {
    "nas": "536284719",
    "code": "M4N8P2",
    "law_id": "L2025-001",
    "hash": "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b",
    "vote": "non"
  }
]
```

## Summary Statistics

After generation completes, the service displays:

- Total hashes generated
- Law ID used
- Output directory
- Vote distribution (oui vs non percentages)
- List of generated files with sizes
- Total size of all files

Example output:

```
============================================================
GENERATION COMPLETE
============================================================
Total hashes generated: 2,500,000
Law ID: L2025-001
Output directory: /path/to/output

Vote distribution:
  - Oui: 1,250,234 (50.01%)
  - Non: 1,249,766 (49.99%)

Files created: 3
  1. hashes_shard_0000.json (125.45 MB)
  2. hashes_shard_0001.json (125.48 MB)
  3. hashes_shard_0002.json (62.73 MB)

Total size: 313.66 MB
============================================================
```

## Security Considerations

- Hashes use SHA-256 for cryptographic security
- Random generation uses Python's `random` module (sufficient for testing)
- For production use, consider using `secrets` module for cryptographically secure random generation
- Each hash is unique based on the NAS|Code|Law_ID combination

## Performance

- Generation speed: ~100,000-500,000 hashes per second (depends on hardware)
- Memory efficient: Sharded output prevents memory overflow
- Progress tracking: Real-time progress bar with tqdm

## Use Cases

1. **Testing**: Generate small datasets for development and testing
2. **Simulation**: Create large datasets to simulate real voting scenarios
3. **Distribution**: Shard files can be distributed across multiple servers
4. **Load Testing**: Generate millions of hashes to test system performance

## Integration

The generated hash files can be:

- Loaded into databases for authentication
- Distributed to voting nodes in the network
- Used for voter lookup during authentication
- Analyzed for vote counting and validation

## Troubleshooting

### Issue: Out of memory
**Solution**: Reduce the shard size using `--shard-size`

### Issue: Slow generation
**Solution**: Check system resources, consider generating in batches

### Issue: tqdm not found
**Solution**: Install requirements: `pip install -r requirements.txt`

## License

This service is part of the distributed voting system project.

## Contributing

Ensure all changes maintain:
- The exact hash format: `{nas}|{code.upper()}|{law_id}`
- 9-digit NAS (digits only)
- 6-character uppercase alphanumeric codes
- SHA-256 hash algorithm
