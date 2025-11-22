# Quick Start Guide

Get the distributed voting system running locally in 5 minutes.

## Prerequisites

- Docker and Docker Compose installed
- 4GB+ available RAM
- Ports 5432, 5672, 6379, 8000, 9090, 3001, 15672 available

## Option 1: Using Make (Recommended)

```bash
# 1. Start all services
make up

# 2. Wait ~30 seconds, then initialize the system
make init

# 3. Check service health
make health

# 4. View service URLs
make urls

# 5. View logs
make logs
```

## Option 2: Using Docker Compose Directly

```bash
# 1. Start all services
docker-compose up -d

# 2. Wait ~30 seconds for services to be healthy
docker-compose ps

# 3. Initialize the system
./scripts/init_system.sh

# 4. Check services are running
docker-compose ps
```

## Verify Setup

### Check Service Health

```bash
# Using Make
make health

# Or manually
curl http://localhost:8000/health
curl -u guest:guest http://localhost:15672/api/overview
docker-compose exec redis redis-cli ping
docker-compose exec postgres psql -U voting_user -d voting -c "SELECT 1"
```

### Access Web Interfaces

1. **API Documentation**: http://localhost:8000/docs
2. **RabbitMQ Management**: http://localhost:15672 (guest/guest)
3. **Grafana Dashboards**: http://localhost:3001 (admin/admin)
4. **Prometheus**: http://localhost:9090

## Test the System

### Submit a Test Vote

```bash
# Submit a vote via API
curl -X POST http://localhost:8000/api/v1/vote \
  -H "Content-Type: application/json" \
  -d '{
    "nas": "123456789",
    "code": "ABC123",
    "law_id": "LAW001",
    "vote": "oui"
  }'
```

### Check Vote Processing

```bash
# Check validation queue
curl -u guest:guest http://localhost:15672/api/queues/%2F/validation_queue

# Check database for votes
docker-compose exec postgres psql -U voting_user -d voting \
  -c "SELECT * FROM vote_results;"

# Check Redis for hash count
docker-compose exec redis redis-cli SCARD valid_hashes
```

## Scale Workers

```bash
# Scale validation workers to 5
make scale-workers WORKERS=5

# Or with docker-compose
docker-compose up -d --scale validation-worker=5
```

## View Logs

```bash
# All services
make logs

# Specific service
make logs-api
make logs-worker

# Or with docker-compose
docker-compose logs -f ingestion-api
```

## Common Commands

```bash
make help           # Show all available commands
make stats          # Show system statistics
make ps             # Show running containers
make restart        # Restart all services
make down           # Stop all services
make urls           # Show service URLs
```

## Load Test Data

### Generate Sample Hashes

```bash
# Generate 1000 sample hashes
cd services/hash_generator
python generate_hashes.py --count 1000 --output ../../data/hashes/sample.json

# Load into Redis
python ../../scripts/load_hashes_to_redis.py
```

### Load Sample Votes

See `data/samples/` directory for sample vote data.

## Monitoring

### Grafana Dashboards

1. Open http://localhost:3001
2. Login: admin/admin
3. Navigate to Dashboards
4. View "Voting System Overview"

### Key Metrics to Watch

- **Votes/second**: Current ingestion rate
- **Queue depth**: Messages waiting to be processed
- **Duplicate rate**: Percentage of duplicate votes
- **Response time**: API latency

## Troubleshooting

### Services not starting

```bash
# Check logs
make logs

# Check Docker resources
docker system df

# Restart services
make restart
```

### Port conflicts

Edit `docker-compose.yml` and change host ports:
```yaml
ports:
  - "8001:8000"  # Change 8000 to 8001
```

### Database errors

```bash
# Check PostgreSQL logs
docker-compose logs postgres

# Verify database is initialized
docker-compose exec postgres psql -U voting_user -d voting -c "\dt"
```

### Redis connection errors

```bash
# Check Redis is running
docker-compose exec redis redis-cli ping

# Check Redis logs
docker-compose logs redis
```

## Next Steps

1. **Load Production Hashes**: Generate and load your full hash database
2. **Configure Monitoring**: Set up Grafana dashboards and alerts
3. **Run Load Tests**: Test system under peak load
4. **Deploy to Kubernetes**: See `k8s/` directory for production deployment
5. **Read Architecture**: Review `ARCHITECTURE.md` for system design

## Stop Services

```bash
# Stop (keep data)
make down

# Stop and remove all data
make down-clean  # WARNING: Deletes all volumes!
```

## Getting Help

- Check service logs: `make logs`
- View health status: `make health`
- See statistics: `make stats`
- Read detailed docs: `DOCKER_SETUP.md`
- Review architecture: `ARCHITECTURE.md`

## Development Mode

For development with hot-reload:

```bash
# Start in development mode
make dev

# This starts all services plus:
# - Source code mounted as volumes
# - Auto-reload on code changes
# - Debug logging enabled
# - Additional monitoring exporters
# - Adminer for database management
```
