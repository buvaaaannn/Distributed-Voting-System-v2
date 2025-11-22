# Docker Setup Guide

This guide explains how to set up and run the distributed voting system using Docker Compose.

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- At least 4GB of available RAM
- Python 3.9+ (for running utility scripts)

## Quick Start

### 1. Start All Services

```bash
# Start all services in the background
docker-compose up -d

# View logs
docker-compose logs -f

# View logs for specific service
docker-compose logs -f ingestion-api
```

### 2. Initialize the System

After all services are running (wait ~30 seconds for health checks):

```bash
# Run initialization script
./scripts/init_system.sh
```

This script will:
- Wait for all services to be healthy
- Create RabbitMQ exchanges and queues
- Load voter hashes into Redis
- Verify database schema

### 3. Verify Setup

Check service health:

```bash
# Check all containers are running
docker-compose ps

# Check Redis
docker-compose exec redis redis-cli ping

# Check RabbitMQ
curl -u guest:guest http://localhost:15672/api/overview

# Check PostgreSQL
docker-compose exec postgres psql -U voting_user -d voting -c "\dt"

# Check API health
curl http://localhost:8000/health
```

## Service URLs

- **Ingestion API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **RabbitMQ Management**: http://localhost:15672 (guest/guest)
- **Grafana Dashboards**: http://localhost:3001 (admin/admin)
- **Prometheus**: http://localhost:9090

## Scaling Services

### Scale Validation Workers

The validation worker service is designed to be scaled horizontally:

```bash
# Scale to 5 workers
docker-compose up -d --scale validation-worker=5

# Scale to 10 workers
docker-compose up -d --scale validation-worker=10

# Check running workers
docker-compose ps validation-worker
```

## Loading Voter Hashes

### Manual Hash Loading

If you need to reload hashes or load additional hash files:

```bash
# Load hashes from data/hashes/ directory
python3 scripts/load_hashes_to_redis.py \
  --redis-host localhost \
  --redis-port 6379 \
  --batch-size 10000

# Clear existing hashes and reload
python3 scripts/load_hashes_to_redis.py --clear

# Use different hash directory
python3 scripts/load_hashes_to_redis.py --hash-dir /path/to/hashes
```

### Hash File Formats

The loader supports two formats:

**JSON format** (`data/hashes/shard_*.json`):
```json
{
  "hashes": [
    "hash1",
    "hash2",
    "hash3"
  ]
}
```

**Text format** (`data/hashes/shard_*.txt`):
```
hash1
hash2
hash3
```

## Data Persistence

All data is persisted in Docker volumes:

```bash
# List volumes
docker volume ls | grep version2

# Inspect volume
docker volume inspect version2_postgres-data

# Backup PostgreSQL data
docker-compose exec postgres pg_dump -U voting_user voting > backup.sql

# Restore PostgreSQL data
docker-compose exec -T postgres psql -U voting_user voting < backup.sql
```

## Monitoring

### Grafana Dashboards

1. Open http://localhost:3001
2. Login with `admin/admin`
3. Navigate to Dashboards
4. View pre-configured voting system dashboards

### Prometheus Metrics

View raw metrics:
- Prometheus UI: http://localhost:9090
- Query metrics: `votes_received_total`, `votes_validated_total`, etc.

### RabbitMQ Monitoring

1. Open http://localhost:15672
2. Login with `guest/guest`
3. View queues, exchanges, and message rates

## Common Operations

### View Service Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f ingestion-api

# Last 100 lines
docker-compose logs --tail=100 validation-worker
```

### Restart Services

```bash
# Restart all services
docker-compose restart

# Restart specific service
docker-compose restart ingestion-api

# Restart with rebuild
docker-compose up -d --build ingestion-api
```

### Stop Services

```bash
# Stop all services (keep data)
docker-compose stop

# Stop and remove containers (keep data)
docker-compose down

# Stop and remove containers + volumes (DELETE ALL DATA)
docker-compose down -v
```

### Database Operations

```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U voting_user -d voting

# Run SQL query
docker-compose exec postgres psql -U voting_user -d voting -c "SELECT * FROM vote_results;"

# View tables
docker-compose exec postgres psql -U voting_user -d voting -c "\dt"
```

### Redis Operations

```bash
# Connect to Redis CLI
docker-compose exec redis redis-cli

# Check number of valid hashes
docker-compose exec redis redis-cli SCARD valid_hashes

# Check number of voted hashes
docker-compose exec redis redis-cli SCARD voted_hashes

# View memory usage
docker-compose exec redis redis-cli INFO memory
```

### RabbitMQ Operations

```bash
# List queues
curl -u guest:guest http://localhost:15672/api/queues

# Purge a queue
curl -u guest:guest -X DELETE http://localhost:15672/api/queues/%2F/validation_queue/contents

# View queue details
curl -u guest:guest http://localhost:15672/api/queues/%2F/validation_queue
```

## Troubleshooting

### Services Won't Start

```bash
# Check Docker daemon
docker info

# Check available resources
docker system df

# View detailed logs
docker-compose logs --tail=50
```

### Out of Memory

```bash
# Check memory usage
docker stats

# Reduce worker count
docker-compose up -d --scale validation-worker=2

# Increase Docker memory limit in Docker Desktop settings
```

### Database Connection Issues

```bash
# Check PostgreSQL logs
docker-compose logs postgres

# Verify connection
docker-compose exec postgres psql -U voting_user -d voting -c "SELECT 1;"

# Check environment variables
docker-compose exec ingestion-api env | grep POSTGRES
```

### Redis Connection Issues

```bash
# Check Redis logs
docker-compose logs redis

# Test connection
docker-compose exec redis redis-cli ping

# Check Redis info
docker-compose exec redis redis-cli INFO
```

### RabbitMQ Connection Issues

```bash
# Check RabbitMQ logs
docker-compose logs rabbitmq

# Check cluster status
docker-compose exec rabbitmq rabbitmq-diagnostics status

# Check connections
curl -u guest:guest http://localhost:15672/api/connections
```

### Port Conflicts

If ports are already in use, you can change them in `docker-compose.yml`:

```yaml
ports:
  - "8001:8000"  # Change host port (left side) to 8001
```

## Development Workflow

### Hot Reload for Development

For development, you can mount source code as volumes:

```yaml
# docker-compose.override.yml
services:
  ingestion-api:
    volumes:
      - ./services/ingestion_api:/app
```

### Rebuild After Code Changes

```bash
# Rebuild specific service
docker-compose build ingestion-api

# Rebuild and restart
docker-compose up -d --build ingestion-api

# Rebuild all services
docker-compose build
```

### Run Tests in Container

```bash
# Run tests in ingestion-api container
docker-compose exec ingestion-api pytest

# Run tests in validation-worker container
docker-compose exec validation-worker pytest
```

## Performance Tuning

### Optimize for High Load

```yaml
# docker-compose.yml
services:
  validation-worker:
    environment:
      - WORKER_CONCURRENCY=20
      - WORKER_PREFETCH_COUNT=200
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
```

### Scale horizontally

```bash
# Scale to 10 workers with 20 concurrent tasks each
docker-compose up -d --scale validation-worker=10
```

## Cleanup

### Remove All Data

```bash
# Stop and remove everything including volumes
docker-compose down -v

# Remove all voting-related images
docker images | grep voting | awk '{print $3}' | xargs docker rmi

# Clean up unused resources
docker system prune -a
```

## Next Steps

1. Generate voter hashes using `services/hash_generator/`
2. Load a sample dataset for testing
3. Configure Grafana dashboards
4. Set up production deployment (see `k8s/` directory)
5. Run load tests (see `tests/load/`)

## Additional Resources

- [Architecture Documentation](ARCHITECTURE.md)
- [API Documentation](http://localhost:8000/docs) (when running)
- [Kubernetes Deployment](k8s/README.md)
- [Monitoring Guide](monitoring/README.md)
