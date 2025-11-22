# Distributed Voting System - Architecture v2

## Overview

Production-grade distributed voting system designed to handle 8 million concurrent voters across Canada in a 24-hour voting window.

## Requirements

- **Scale**: 8M votes in 24 hours (~92 votes/sec average, 500-1000/sec peak)
- **Security**: Offline hash database, no PII in voting system
- **Reliability**: No vote loss, duplicate detection with voter feedback
- **Deployment**: Docker/Kubernetes for horizontal scaling

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         OFFLINE PHASE                            │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Hash Generator: Pre-generates 8M hashes from NAS+Code     │ │
│  │  Output: hash_database.json (sharded for distribution)     │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                         ONLINE PHASE                             │
│                                                                   │
│  ┌──────────────┐                                                │
│  │  Web UI/API  │ ← Voter submits: NAS, Code, Law_ID, Vote      │
│  └──────┬───────┘                                                │
│         │                                                         │
│         ▼                                                         │
│  ┌─────────────────┐                                            │
│  │ Ingestion API   │  FastAPI - Validates format, generates hash│
│  │ (FastAPI)       │  Returns: 202 Accepted or 400 Bad Request  │
│  └────────┬────────┘                                            │
│           │                                                      │
│           │ Publishes vote to queue                             │
│           ▼                                                      │
│  ┌─────────────────┐                                            │
│  │   RabbitMQ      │  Reliable message queue                   │
│  │  Message Queue  │  Exchange: votes / Queue: validation      │
│  └────────┬────────┘                                            │
│           │                                                      │
│           │ Multiple workers consume                            │
│           ▼                                                      │
│  ┌─────────────────────────────────────────┐                   │
│  │  Validation Workers (Scalable)          │                   │
│  │  1. Check hash in Redis (fast lookup)   │                   │
│  │  2. Check duplicate (Redis SET)          │                   │
│  │  3. If duplicate: increment counter,     │                   │
│  │     publish to review queue              │                   │
│  │  4. If valid: publish to aggregation     │                   │
│  └─────────┬─────────────────┬─────────────┘                   │
│            │                 │                                   │
│            │                 │                                   │
│   Valid votes                Duplicates/Invalid                 │
│            │                 │                                   │
│            ▼                 ▼                                   │
│  ┌──────────────┐   ┌───────────────────┐                      │
│  │ Aggregation  │   │  Review Queue     │                      │
│  │   Service    │   │  (Manual Audit)   │                      │
│  │              │   └───────────────────┘                      │
│  │ - Count votes│                                               │
│  │ - Update DB  │                                               │
│  └──────┬───────┘                                               │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────────┐                                          │
│  │   PostgreSQL     │  Persistent Storage                      │
│  │                  │  - vote_results (law_id, oui, non)       │
│  │                  │  - vote_audit (hash, timestamp, status)  │
│  │                  │  - duplicate_attempts (hash, count)      │
│  └──────────────────┘                                          │
│                                                                  │
│  ┌──────────────────┐                                          │
│  │  Redis Cluster   │  Fast In-Memory Storage                  │
│  │                  │  - valid_hashes (SET): all 8M hashes     │
│  │                  │  - voted_hashes (SET): deduplication     │
│  │                  │  - duplicate_count:{hash} (counter)      │
│  └──────────────────┘                                          │
│                                                                  │
│  ┌──────────────────────────────────────────┐                  │
│  │  Monitoring Stack                        │                  │
│  │  - Prometheus: Metrics collection        │                  │
│  │  - Grafana: Dashboards                   │                  │
│  │  Metrics: votes/sec, latency, errors,    │                  │
│  │           queue depth, duplicate rate     │                  │
│  └──────────────────────────────────────────┘                  │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Vote Submission
```
POST /api/v1/vote
{
  "nas": "123456789",
  "code": "ABC123",
  "law_id": "L2025-001",
  "vote": "oui"
}

→ API generates hash: sha256("123456789|ABC123|L2025-001")
→ Publishes to RabbitMQ: {hash, law_id, vote, timestamp}
→ Returns 202 Accepted {request_id: "uuid"}
```

### 2. Validation (Worker)
```
1. Check hash in Redis SET 'valid_hashes'
   - If not found: reject → review queue

2. Check hash in Redis SET 'voted_hashes'
   - If found: duplicate!
     → INCR duplicate_count:{hash}
     → Publish to review queue
     → Response: {status: "duplicate", attempt_count: N}

3. If valid & new:
   - SADD voted_hashes {hash}
   - Publish to aggregation queue
   - Log to audit table
```

### 3. Aggregation
```
- Consume from aggregation queue
- UPDATE vote_results SET oui_count = oui_count + 1
  WHERE law_id = 'L2025-001'
- Emit metrics to Prometheus
```

## Components Detail

### Hash Generator (Offline)
**File**: `services/hash_generator/generator.py`
- Input: CSV with 8M rows (NAS, Code, Law_ID)
- Output: Sharded JSON files (1M hashes each)
- Distribution: Load into Redis on startup

### Vote Ingestion API
**File**: `services/ingestion_api/main.py`
- FastAPI with async support
- Endpoints:
  - `POST /api/v1/vote` - Submit vote
  - `GET /api/v1/health` - Health check
  - `GET /api/v1/results/{law_id}` - Get results
- Rate limiting: 1000 req/sec per instance
- Horizontal scaling: 10+ instances behind load balancer

### Validation Workers
**File**: `services/validation_worker/worker.py`
- Consumes from RabbitMQ
- Redis operations (SISMEMBER, SADD, INCR)
- Publishes to aggregation or review queue
- Scalable: 20+ workers for peak load

### Aggregation Service
**File**: `services/aggregation/aggregator.py`
- Consumes from aggregation queue
- Batch updates to PostgreSQL (100 votes/batch)
- Emits metrics every second

### Message Queue (RabbitMQ)
**Exchanges**:
- `votes.exchange` (topic)

**Queues**:
- `votes.validation` - Pending validation
- `votes.aggregation` - Valid votes to count
- `votes.review` - Duplicates & invalid for audit

**Durability**: Persistent messages, durable queues

### Redis Cluster
**Data Structures**:
```
valid_hashes: SET (8M members)
voted_hashes: SET (grows to 8M)
duplicate_count:{hash}: STRING (counter)
```

**Memory**: ~2GB for 8M hashes + voted set

### PostgreSQL Schema
```sql
CREATE TABLE vote_results (
  law_id VARCHAR(50) PRIMARY KEY,
  oui_count BIGINT DEFAULT 0,
  non_count BIGINT DEFAULT 0,
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE vote_audit (
  id BIGSERIAL PRIMARY KEY,
  vote_hash VARCHAR(64) NOT NULL,
  law_id VARCHAR(50) NOT NULL,
  vote VARCHAR(3) NOT NULL,
  status VARCHAR(20) NOT NULL, -- 'accepted', 'duplicate', 'invalid'
  timestamp TIMESTAMP DEFAULT NOW(),
  INDEX idx_hash (vote_hash),
  INDEX idx_law_timestamp (law_id, timestamp)
);

CREATE TABLE duplicate_attempts (
  vote_hash VARCHAR(64) PRIMARY KEY,
  attempt_count INT DEFAULT 1,
  first_attempt TIMESTAMP DEFAULT NOW(),
  last_attempt TIMESTAMP DEFAULT NOW()
);
```

## Deployment

### Development (Docker Compose)
```bash
cd version2
docker-compose up
```

Services:
- ingestion-api: localhost:8000
- rabbitmq-management: localhost:15672
- redis: localhost:6379
- postgres: localhost:5432
- grafana: localhost:3000
- prometheus: localhost:9090

### Production (Kubernetes)
```bash
kubectl apply -f k8s/
```

**Scaling**:
- Ingestion API: 10 replicas (HPA based on CPU/memory)
- Validation Workers: 20 replicas (HPA based on queue depth)
- Aggregation Service: 3 replicas
- Redis: 3-node cluster
- PostgreSQL: 1 master + 2 read replicas

## Security Considerations

1. **No PII Storage**: Only hashes stored, NAS/Code never persisted
2. **Hash Validation**: Pre-generated offline database prevents fake votes
3. **Duplicate Detection**: Redis SET ensures one vote per hash
4. **Audit Trail**: All attempts logged (accepted, duplicate, invalid)
5. **Rate Limiting**: API rate limits prevent spam
6. **TLS**: All inter-service communication encrypted
7. **Network Policies**: K8s network policies restrict access

## Performance Targets

- **Throughput**: 1000 votes/second sustained
- **Latency**: <100ms p95 for vote submission
- **Availability**: 99.9% uptime during voting window
- **Data Loss**: Zero vote loss (RabbitMQ persistence)

## Monitoring Metrics

**Vote Processing**:
- `votes_submitted_total` (counter)
- `votes_validated_total{status="accepted|duplicate|invalid"}` (counter)
- `votes_per_second` (gauge)
- `validation_latency_seconds` (histogram)

**System Health**:
- `rabbitmq_queue_depth{queue}` (gauge)
- `redis_memory_used_bytes` (gauge)
- `postgres_connections` (gauge)
- `api_request_duration_seconds` (histogram)

**Business Metrics**:
- `duplicate_attempts_total` (counter)
- `votes_by_law{law_id,choice}` (gauge)

## Disaster Recovery

1. **RabbitMQ**: Persistent messages survive restarts
2. **Redis**: AOF persistence + snapshots every 60s
3. **PostgreSQL**: Continuous WAL archiving + daily backups
4. **Replay**: Can rebuild voted_hashes SET from vote_audit table

## Testing Strategy

1. **Unit Tests**: Each service component
2. **Integration Tests**: Full vote flow end-to-end
3. **Load Tests**: Simulate 1000 votes/sec for 1 hour
4. **Chaos Tests**: Kill random pods, verify no data loss
5. **Demo Tests**: Web UI workflow with sample votes
