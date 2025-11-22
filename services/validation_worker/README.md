# Validation Worker Service

The validation worker service processes votes from the RabbitMQ validation queue, validates them against Redis, and routes them appropriately.

## Features

- **Vote Validation**: Checks if voter hash exists in valid_hashes Redis set
- **Duplicate Detection**: Prevents duplicate votes using voted_hashes Redis set
- **Audit Logging**: Records all votes in PostgreSQL for compliance
- **Error Handling**: Graceful error handling with message requeuing
- **Metrics**: Prometheus metrics for monitoring
- **Graceful Shutdown**: Handles SIGTERM/SIGINT signals properly

## Architecture

### Processing Flow

1. **Consume** from `votes.validation` queue
2. **Validate Hash**: Check if hash exists in `valid_hashes` Redis SET
   - If invalid → publish to `votes.review` queue with status='invalid'
3. **Check Duplicate**: Check if hash exists in `voted_hashes` Redis SET
   - If duplicate:
     - Increment `duplicate_count:{hash}` counter
     - Publish to `votes.review` queue with status='duplicate' and attempt count
4. **Process Valid Vote**:
   - Add hash to `voted_hashes` SET
   - Insert audit log into PostgreSQL `vote_audit` table
   - Publish to `votes.aggregation` queue
   - ACK message

### Components

- **worker.py**: Main worker logic and message processing
- **redis_client.py**: Redis operations (validation, duplicate checking)
- **rabbitmq_client.py**: RabbitMQ consumer/publisher with auto-reconnect
- **database.py**: PostgreSQL client with connection pooling
- **config.py**: Environment configuration management

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
# RabbitMQ
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASS=guest

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=election_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# Worker
WORKER_ID=worker-1
PREFETCH_COUNT=10
METRICS_PORT=8001
```

## Running Locally

### Prerequisites

- Python 3.11+
- RabbitMQ running
- Redis running
- PostgreSQL running with `vote_audit` table

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run Worker

```bash
python worker.py
```

## Running with Docker

### Build Image

```bash
docker build -t validation-worker:latest .
```

### Run Container

```bash
docker run -d \
  --name validation-worker \
  --env-file .env \
  -p 8001:8001 \
  validation-worker:latest
```

## Metrics

Prometheus metrics available at `http://localhost:8001/metrics`:

- `validation_votes_processed_total{status}`: Total votes processed by status
- `validation_processing_latency_seconds`: Processing time histogram
- `validation_errors_total{error_type}`: Total errors by type
- `validation_queue_size`: Current queue size
- `redis_operations_total{operation,status}`: Redis operation counts
- `database_operations_total{operation,status}`: Database operation counts

## Database Schema

The worker expects the following PostgreSQL table:

```sql
CREATE TABLE vote_audit (
    id SERIAL PRIMARY KEY,
    voter_hash VARCHAR(64) NOT NULL,
    candidate_id INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL,
    vote_timestamp TIMESTAMP NOT NULL,
    processed_timestamp TIMESTAMP NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_vote_audit_voter_hash ON vote_audit(voter_hash);
CREATE INDEX idx_vote_audit_status ON vote_audit(status);
CREATE INDEX idx_vote_audit_timestamp ON vote_audit(vote_timestamp);
```

## Error Handling

- **Invalid JSON**: Message rejected (not requeued)
- **Redis Errors**: Message NACKed and requeued
- **Database Errors**: Redis operation rolled back, message NACKed
- **Connection Errors**: Automatic reconnection with retry logic

## Graceful Shutdown

The worker handles SIGTERM/SIGINT signals:

1. Stops consuming new messages
2. Completes processing current message
3. Closes RabbitMQ connection
4. Closes Redis connection
5. Closes database connections
6. Exits cleanly

## Scaling

Run multiple workers for horizontal scaling:

```bash
# Worker 1
WORKER_ID=worker-1 METRICS_PORT=8001 python worker.py

# Worker 2
WORKER_ID=worker-2 METRICS_PORT=8002 python worker.py

# Worker 3
WORKER_ID=worker-3 METRICS_PORT=8003 python worker.py
```

Each worker processes messages independently from the shared queue.

## Monitoring

### Health Check

Check if worker is processing messages:

```bash
curl http://localhost:8001/metrics | grep validation_votes_processed_total
```

### Queue Size

Monitor queue depth:

```bash
curl http://localhost:8001/metrics | grep validation_queue_size
```

### Error Rate

Monitor error rate:

```bash
curl http://localhost:8001/metrics | grep validation_errors_total
```

## Troubleshooting

### Worker not processing messages

1. Check RabbitMQ connection
2. Verify queue exists and has messages
3. Check Redis connectivity
4. Review worker logs

### High error rate

1. Check Redis availability
2. Verify database connectivity
3. Check message format
4. Review error metrics by type

### Slow processing

1. Increase `PREFETCH_COUNT`
2. Scale horizontally (add more workers)
3. Check database connection pool size
4. Monitor Redis latency

## License

MIT
