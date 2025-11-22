# Vote Aggregation Service - Architecture

## Overview

The Vote Aggregation Service is a high-performance, fault-tolerant microservice responsible for consuming validated votes from RabbitMQ, batching them for efficiency, and updating PostgreSQL with aggregated vote counts.

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Vote Aggregation Service                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐      ┌──────────────┐                   │
│  │   RabbitMQ   │─────▶│   Message    │                   │
│  │   Consumer   │      │   Handler    │                   │
│  └──────────────┘      └──────┬───────┘                   │
│         ▲                     │                            │
│         │                     ▼                            │
│         │              ┌──────────────┐                   │
│    Auto-reconnect      │    Batcher   │                   │
│         │              │  (100 votes  │                   │
│         │              │   or 1 sec)  │                   │
│         │              └──────┬───────┘                   │
│         │                     │                            │
│         │                     ▼                            │
│         │              ┌──────────────┐                   │
│         └──────────────│  PostgreSQL  │                   │
│                        │   UPSERT     │                   │
│                        └──────┬───────┘                   │
│                               │                            │
│                               ▼                            │
│                        ┌──────────────┐                   │
│                        │  Prometheus  │                   │
│                        │   Metrics    │                   │
│                        └──────────────┘                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. aggregator.py - Main Service

**Responsibilities:**
- Initialize and coordinate all components
- Manage message consumption from RabbitMQ
- Implement batching logic (size-based and time-based)
- Handle retry logic with exponential backoff
- Emit Prometheus metrics
- Graceful shutdown handling

**Key Features:**
- Multi-threaded batch processor
- Signal handling (SIGINT, SIGTERM)
- Error tracking and monitoring
- Automatic metric synchronization

**Batching Strategy:**
```python
# Size-based: Process when batch reaches threshold
if len(batch) >= BATCH_SIZE:  # Default: 100
    process_batch()

# Time-based: Process if timeout elapsed
if time_since_last_batch >= BATCH_TIMEOUT:  # Default: 1s
    process_batch()

# Shutdown: Process all remaining votes
on_shutdown():
    process_batch()  # Ensure no votes lost
```

### 2. database.py - PostgreSQL Operations

**Responsibilities:**
- Manage connection pool (2-10 connections)
- Execute UPSERT operations efficiently
- Transaction management
- Schema initialization
- Error handling and recovery

**Key Operations:**

```python
# Batch UPSERT
INSERT INTO vote_results (law_id, oui_count, non_count)
VALUES (%s, %s, %s)
ON CONFLICT (law_id)
DO UPDATE SET
    oui_count = vote_results.oui_count + EXCLUDED.oui_count,
    non_count = vote_results.non_count + EXCLUDED.non_count,
    updated_at = NOW()
```

**Connection Pool:**
- Min: 2 connections (always available)
- Max: 10 connections (scales under load)
- Timeout: 10 seconds
- Auto-reconnect on connection loss

### 3. rabbitmq_client.py - Message Queue Client

**Responsibilities:**
- Connect to RabbitMQ with credentials
- Consume messages from queue
- Acknowledge/reject messages
- Auto-reconnect on connection loss
- QoS management (prefetch)

**QoS Configuration:**
```python
channel.basic_qos(prefetch_count=100)
# Prefetch 100 messages for batching efficiency
```

**Auto-Reconnect:**
```python
while True:
    try:
        consume_messages()
    except ConnectionError:
        reconnect(delay=5s)
```

### 4. config.py - Configuration Management

**Responsibilities:**
- Load environment variables
- Provide default values
- Centralize configuration

**Configuration Categories:**
- RabbitMQ connection settings
- PostgreSQL connection settings
- Batching parameters
- Retry configuration
- Monitoring settings

## Data Flow

### Normal Operation

1. **Message Arrival**
   ```
   RabbitMQ → Consumer → Parse JSON → Add to Batch
   ```

2. **Batch Processing** (triggered by size or timeout)
   ```
   Batch → Aggregate by law_id → Database UPSERT → ACK messages
   ```

3. **Metric Update**
   ```
   Database → Read counts → Update Prometheus gauges
   ```

### Error Handling

1. **Malformed Message**
   ```
   Parse Error → Log error → NACK (no requeue) → Discard
   ```

2. **Database Error**
   ```
   UPSERT fails → Retry (3x, exponential backoff) → Log failure
   ```

3. **Connection Loss**
   ```
   RabbitMQ disconnected → Wait 5s → Reconnect → Resume
   PostgreSQL disconnected → Pool reconnect → Resume
   ```

## Database Schema

### vote_results (Primary Aggregation Table)
```sql
CREATE TABLE vote_results (
    law_id VARCHAR(50) PRIMARY KEY,
    oui_count BIGINT DEFAULT 0,
    non_count BIGINT DEFAULT 0,
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**Indexes:**
- Primary key on `law_id` (unique lookups)
- Index on `updated_at` (recent updates)
- Index on total counts (analytics)

### vote_audit (Audit Log)
```sql
CREATE TABLE vote_audit (
    id BIGSERIAL PRIMARY KEY,
    vote_hash VARCHAR(64) UNIQUE,
    citizen_id VARCHAR(100),
    law_id VARCHAR(50),
    choice VARCHAR(10),
    timestamp TIMESTAMP,
    ...
);
```

**Purpose:**
- Individual vote tracking
- Audit trail
- Duplicate detection reference

### duplicate_attempts (Security)
```sql
CREATE TABLE duplicate_attempts (
    id BIGSERIAL PRIMARY KEY,
    vote_hash VARCHAR(64),
    citizen_id VARCHAR(100),
    law_id VARCHAR(50),
    attempt_timestamp TIMESTAMP,
    ...
);
```

**Purpose:**
- Track duplicate vote attempts
- Security monitoring
- Fraud detection

## Performance Optimization

### 1. Batching
- **Size-based batching**: Reduces database round trips
- **Time-based batching**: Ensures low latency
- **Optimal batch size**: 100 votes (tunable)

### 2. Connection Pooling
- Reuses database connections
- Reduces connection overhead
- Scales with load (2-10 connections)

### 3. UPSERT Operations
- Single query per law_id
- Atomic increment operations
- No read-modify-write race conditions

### 4. Prefetch Count
- Fetches 100 messages at once
- Reduces network round trips
- Enables efficient batching

### 5. Execute Batch
- Uses `psycopg2.extras.execute_batch`
- Page size: 100 (optimized for PostgreSQL)
- Reduces parse overhead

## Monitoring

### Prometheus Metrics

**Counters:**
```python
votes_aggregated_total{law_id, choice}
# Total votes processed per law and choice

batch_size_processed_total
# Total size of all batches

aggregation_errors_total{error_type}
# Errors by type (json_decode, database, etc.)
```

**Gauges:**
```python
current_vote_totals{law_id, choice}
# Real-time vote counts (synced from DB)

batch_processing_duration_seconds
# Time to process last batch
```

### Log Levels

- **DEBUG**: Message details, batch composition
- **INFO**: Batch processing, connections, shutdown
- **WARNING**: Retries, invalid data
- **ERROR**: Database failures, connection errors

## Scalability

### Horizontal Scaling

**Multiple instances can run in parallel:**
```
┌──────────────┐
│ Aggregator 1 │────┐
└──────────────┘    │
                    ▼
┌──────────────┐  ┌──────────┐  ┌────────────┐
│ Aggregator 2 │─▶│ RabbitMQ │  │ PostgreSQL │
└──────────────┘  └──────────┘  └────────────┘
                    ▲
┌──────────────┐    │
│ Aggregator 3 │────┘
└──────────────┘
```

**Benefits:**
- Load distribution
- Fault tolerance
- Higher throughput

**Considerations:**
- PostgreSQL can handle concurrent UPSERTs
- RabbitMQ distributes messages (round-robin)
- Each instance maintains its own batch

### Vertical Scaling

**Tune for higher load:**
```env
BATCH_SIZE=500                  # Larger batches
POSTGRES_MAX_CONNECTIONS=20     # More DB connections
RABBITMQ_PREFETCH_COUNT=500     # Higher prefetch
```

## Fault Tolerance

### 1. Message Durability
- Queue declared as durable
- Messages marked persistent
- No data loss on broker restart

### 2. Acknowledgment Strategy
- Manual ACK after database commit
- Batch ACK (multiple=True) for efficiency
- NACK with requeue on transient errors

### 3. Retry Logic
```python
for attempt in range(MAX_RETRY_ATTEMPTS):
    try:
        process_batch()
        break
    except DatabaseError:
        delay = RETRY_DELAY * (2 ** attempt)
        time.sleep(delay)
```

### 4. Graceful Shutdown
```python
def shutdown():
    1. Stop accepting new messages
    2. Process remaining batch
    3. Close RabbitMQ connection
    4. Close database pool
    5. Exit cleanly
```

## Security Considerations

### 1. Database Access
- Use dedicated user with minimal permissions
- Connection via credentials (not superuser)
- SSL/TLS support for connections

### 2. Message Validation
- JSON schema validation
- Required field checks
- Type validation

### 3. Network Security
- RabbitMQ authentication required
- PostgreSQL authentication required
- No plaintext credentials in code

### 4. Audit Trail
- All votes logged to `vote_audit`
- Duplicate attempts tracked
- Timestamps for all operations

## Deployment

### Docker
```bash
docker build -t vote-aggregator .
docker run -d \
  -e RABBITMQ_HOST=rabbitmq \
  -e POSTGRES_HOST=postgres \
  -p 8001:8001 \
  vote-aggregator
```

### Docker Compose
```bash
docker-compose up -d
```

Includes:
- PostgreSQL (with init script)
- RabbitMQ (with management UI)
- Aggregator service
- Prometheus (metrics)
- Grafana (visualization)

### Kubernetes
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vote-aggregator
spec:
  replicas: 3
  ...
```

## Testing

### Unit Tests
```bash
pytest tests/test_database.py
pytest tests/test_batching.py
```

### Integration Tests
```bash
# Start dependencies
docker-compose up -d postgres rabbitmq

# Run integration tests
pytest tests/integration/
```

### Load Testing
```bash
# Publish test votes
python test_publisher.py -n 10000

# Monitor metrics
curl http://localhost:8001/metrics
```

## Maintenance

### Database Maintenance
```sql
-- Vacuum analyze for performance
VACUUM ANALYZE vote_results;

-- Monitor table size
SELECT pg_size_pretty(pg_total_relation_size('vote_results'));

-- Check index usage
SELECT * FROM pg_stat_user_indexes WHERE relname = 'vote_results';
```

### RabbitMQ Maintenance
```bash
# Check queue depth
rabbitmqctl list_queues

# Purge queue (if needed)
rabbitmqctl purge_queue votes.aggregation
```

### Log Rotation
```bash
# Configure logrotate for application logs
/var/log/aggregator/*.log {
    daily
    rotate 7
    compress
    delaycompress
}
```

## Future Enhancements

1. **Dead Letter Queue**: Move failed batches to DLQ
2. **Distributed Tracing**: OpenTelemetry integration
3. **Cache Layer**: Redis for frequently accessed counts
4. **Partitioning**: Partition vote_results by date
5. **Compression**: Compress old audit logs
6. **Real-time Dashboard**: WebSocket updates for live results
