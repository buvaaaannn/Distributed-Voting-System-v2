# Vote Aggregation Service

The aggregation service consumes validated votes from RabbitMQ, batches them for efficiency, and updates PostgreSQL with aggregated vote counts.

## Features

- **Batch Processing**: Collects votes in batches (100 votes or 1 second timeout)
- **Efficient Database Updates**: Uses UPSERT operations with `INSERT ... ON CONFLICT`
- **Retry Logic**: Automatic retry with exponential backoff for failed batches
- **Prometheus Metrics**: Comprehensive metrics for monitoring
- **Auto-Reconnect**: Automatic reconnection to RabbitMQ on connection loss
- **Graceful Shutdown**: Processes remaining votes before shutdown
- **Connection Pooling**: PostgreSQL connection pool for performance

## Architecture

```
RabbitMQ (votes.aggregation)
    ↓
Aggregator (batching)
    ↓
PostgreSQL (vote_results table)
    ↓
Prometheus Metrics
```

## Database Schema

### vote_results
Primary aggregation table storing vote counts per law:
- `law_id` (PK): Law identifier
- `oui_count`: Count of "oui" votes
- `non_count`: Count of "non" votes
- `updated_at`: Last update timestamp

### vote_audit
Audit log of individual votes:
- `vote_hash` (UNIQUE): Hash of the vote
- `citizen_id`: Voter identifier
- `law_id`: Law identifier
- `choice`: Vote choice (oui/non)
- `timestamp`: Vote timestamp

### duplicate_attempts
Tracks duplicate vote attempts:
- `vote_hash`: Reference to original vote
- `citizen_id`: Voter who attempted
- `attempt_timestamp`: When attempt occurred

## Prometheus Metrics

- `votes_aggregated_total{law_id, choice}`: Total votes aggregated (counter)
- `current_vote_totals{law_id, choice}`: Current vote counts (gauge)
- `batch_processing_duration_seconds`: Batch processing time (gauge)
- `batch_size_processed_total`: Total votes in processed batches (counter)
- `aggregation_errors_total{error_type}`: Aggregation errors (counter)

## Configuration

Environment variables (see `.env.example`):

### RabbitMQ
- `RABBITMQ_HOST`: RabbitMQ host (default: localhost)
- `RABBITMQ_PORT`: RabbitMQ port (default: 5672)
- `RABBITMQ_USER`: Username (default: guest)
- `RABBITMQ_PASSWORD`: Password (default: guest)
- `RABBITMQ_QUEUE`: Queue name (default: votes.aggregation)
- `RABBITMQ_PREFETCH_COUNT`: Prefetch count (default: 100)

### PostgreSQL
- `POSTGRES_HOST`: PostgreSQL host (default: localhost)
- `POSTGRES_PORT`: PostgreSQL port (default: 5432)
- `POSTGRES_DB`: Database name (default: election_votes)
- `POSTGRES_USER`: Username (default: postgres)
- `POSTGRES_PASSWORD`: Password
- `POSTGRES_MIN_CONNECTIONS`: Min pool size (default: 2)
- `POSTGRES_MAX_CONNECTIONS`: Max pool size (default: 10)

### Batching
- `BATCH_SIZE`: Votes per batch (default: 100)
- `BATCH_TIMEOUT_SECONDS`: Batch timeout (default: 1.0)

### Retry
- `MAX_RETRY_ATTEMPTS`: Max retries (default: 3)
- `RETRY_DELAY_SECONDS`: Initial retry delay (default: 1.0)

### Monitoring
- `PROMETHEUS_PORT`: Metrics port (default: 8001)
- `LOG_LEVEL`: Logging level (default: INFO)

## Installation

### Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment:
```bash
cp .env.example .env
# Edit .env with your settings
```

3. Initialize database:
```bash
psql -U postgres -d election_votes -f init_db.sql
```

4. Run the service:
```bash
python aggregator.py
```

### Docker

1. Build image:
```bash
docker build -t vote-aggregator .
```

2. Run container:
```bash
docker run -d \
  --name vote-aggregator \
  -e RABBITMQ_HOST=rabbitmq \
  -e POSTGRES_HOST=postgres \
  -e POSTGRES_PASSWORD=secret \
  -p 8001:8001 \
  vote-aggregator
```

### Docker Compose

```yaml
version: '3.8'

services:
  aggregator:
    build: .
    environment:
      RABBITMQ_HOST: rabbitmq
      POSTGRES_HOST: postgres
      POSTGRES_PASSWORD: secret
    ports:
      - "8001:8001"
    depends_on:
      - rabbitmq
      - postgres
```

## Usage

### Message Format

The service expects JSON messages from RabbitMQ:

```json
{
  "vote_hash": "abc123...",
  "citizen_id": "citizen-123",
  "law_id": "law-001",
  "choice": "oui",
  "timestamp": "2025-11-14T12:00:00Z"
}
```

### Querying Results

```sql
-- Get vote counts for a specific law
SELECT * FROM vote_results WHERE law_id = 'law-001';

-- Get vote statistics
SELECT * FROM vote_statistics;

-- Find top voted laws
SELECT law_id, total_votes
FROM vote_statistics
ORDER BY total_votes DESC
LIMIT 10;
```

### Monitoring

Access Prometheus metrics:
```bash
curl http://localhost:8001/metrics
```

## Batch Processing

The service uses intelligent batching:

1. **Size-based**: Processes when batch reaches 100 votes
2. **Time-based**: Processes every 1 second if votes are pending
3. **Shutdown**: Processes all remaining votes on graceful shutdown

This ensures low latency while maintaining high throughput.

## Error Handling

### Retry Logic
- Failed batches retry up to 3 times
- Exponential backoff: 1s, 2s, 4s
- After max retries, errors are logged and tracked

### Connection Recovery
- RabbitMQ: Auto-reconnect on connection loss
- PostgreSQL: Connection pool handles reconnection

### Message Handling
- Malformed JSON: Rejected without requeue
- Processing errors: Requeued for retry
- Successful processing: Acknowledged in batch

## Performance

### Optimizations
- Connection pooling (PostgreSQL)
- Batch UPSERT operations
- Prefetch count of 100
- Execute batch with page size 100
- Efficient indexing

### Capacity
- Processes ~10,000 votes/second (depending on hardware)
- Batch size tunable for throughput vs latency
- Horizontal scaling supported (multiple instances)

## Graceful Shutdown

The service handles SIGINT and SIGTERM:

1. Stops accepting new messages
2. Processes remaining votes in batch
3. Closes RabbitMQ connection
4. Closes database connections
5. Exits cleanly

```bash
# Graceful shutdown
kill -TERM <pid>

# Or with Docker
docker stop vote-aggregator
```

## Troubleshooting

### High latency
- Reduce `BATCH_TIMEOUT_SECONDS`
- Increase database connection pool size

### High load
- Increase `BATCH_SIZE`
- Scale horizontally (multiple instances)

### Connection errors
- Check RabbitMQ/PostgreSQL availability
- Verify credentials and network connectivity

### Memory usage
- Reduce `BATCH_SIZE`
- Reduce `POSTGRES_MAX_CONNECTIONS`

## Development

### Running tests
```bash
pytest tests/
```

### Code formatting
```bash
black .
flake8 .
```

### Type checking
```bash
mypy *.py
```

## License

MIT License
