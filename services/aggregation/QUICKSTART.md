# Quick Start Guide - Vote Aggregation Service

## Prerequisites

- Docker and Docker Compose installed
- Python 3.11+ (for local development)
- PostgreSQL 15+ (for local development)
- RabbitMQ 3.12+ (for local development)

## Quick Start with Docker Compose (Recommended)

### 1. Start All Services

```bash
docker-compose up -d
```

This starts:
- PostgreSQL (port 5432)
- RabbitMQ (port 5672, management UI: 15672)
- Vote Aggregator (metrics port 8001)
- Prometheus (port 9090)
- Grafana (port 3000)

### 2. Check Service Status

```bash
docker-compose ps
```

All services should show "healthy" or "running".

### 3. Verify Database Schema

```bash
docker exec election-postgres psql -U postgres -d election_votes -c "\dt"
```

You should see tables: `vote_results`, `vote_audit`, `duplicate_attempts`, etc.

### 4. Send Test Votes

```bash
# Install dependencies for test script
pip install pika

# Publish 1,000 test votes
python test_publisher.py -n 1000
```

### 5. Check Results

**In Database:**
```bash
docker exec election-postgres psql -U postgres -d election_votes -c "SELECT * FROM vote_statistics;"
```

**Via Prometheus Metrics:**
```bash
curl http://localhost:8001/metrics | grep current_vote_totals
```

**In RabbitMQ Management UI:**
- Open: http://localhost:15672
- Login: guest/guest
- Check queue `votes.aggregation`

### 6. Monitor Logs

```bash
# Follow aggregator logs
docker-compose logs -f aggregator

# Check for errors
docker-compose logs aggregator | grep ERROR
```

### 7. View Metrics in Grafana

1. Open: http://localhost:3000
2. Login: admin/admin
3. Add Prometheus data source: http://prometheus:9090
4. Create dashboard with metrics:
   - `votes_aggregated_total`
   - `current_vote_totals`
   - `batch_processing_duration_seconds`

### 8. Stop Services

```bash
docker-compose down
```

To remove data volumes:
```bash
docker-compose down -v
```

---

## Local Development Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Start Infrastructure

```bash
# PostgreSQL
docker run -d --name postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=election_votes \
  -p 5432:5432 \
  postgres:15-alpine

# RabbitMQ
docker run -d --name rabbitmq \
  -p 5672:5672 \
  -p 15672:15672 \
  rabbitmq:3.12-management-alpine
```

### 3. Initialize Database

```bash
psql -h localhost -U postgres -d election_votes -f init_db.sql
```

Or:
```bash
make init-db
```

### 4. Configure Environment

```bash
cp .env.example .env
# Edit .env with your settings
```

### 5. Run Aggregator

```bash
python aggregator.py
```

Or:
```bash
make run
```

### 6. Publish Test Votes

In another terminal:
```bash
python test_publisher.py -n 1000
```

Or:
```bash
make publish-test-votes
```

---

## Common Tasks

### Check Vote Counts

```bash
# Using make
make check-db

# Direct SQL
docker exec election-postgres psql -U postgres -d election_votes \
  -c "SELECT law_id, oui_count, non_count, (oui_count + non_count) as total FROM vote_results ORDER BY total DESC;"
```

### Check RabbitMQ Queue

```bash
# Using make
make check-queue

# Direct command
docker exec election-rabbitmq rabbitmqctl list_queues name messages consumers
```

### View Prometheus Metrics

```bash
# Using make
make metrics

# Direct curl
curl http://localhost:8001/metrics
```

### Restart Aggregator

```bash
docker-compose restart aggregator
```

### Scale Aggregators (Multiple Instances)

```bash
docker-compose up -d --scale aggregator=3
```

### View Aggregator Logs

```bash
docker-compose logs -f aggregator
```

---

## Load Testing

### Publish Large Volume

```bash
# 10,000 votes
python test_publisher.py -n 10000

# 100,000 votes (stress test)
python test_publisher.py -n 100000
```

### Monitor Performance

```bash
# Watch metrics update
watch -n 1 'curl -s http://localhost:8001/metrics | grep votes_aggregated_total'

# Monitor database
watch -n 1 'docker exec election-postgres psql -U postgres -d election_votes -c "SELECT * FROM vote_statistics;"'
```

---

## Troubleshooting

### Aggregator Won't Start

**Check logs:**
```bash
docker-compose logs aggregator
```

**Common issues:**
- Database not ready: Wait 30s for PostgreSQL to initialize
- RabbitMQ not ready: Check `docker-compose ps`
- Port conflict: Change PROMETHEUS_PORT in docker-compose.yml

### No Votes Being Processed

**Check queue depth:**
```bash
docker exec election-rabbitmq rabbitmqctl list_queues
```

**Check aggregator logs:**
```bash
docker-compose logs -f aggregator
```

**Verify connection:**
- PostgreSQL: `docker exec election-postgres pg_isready`
- RabbitMQ: `docker exec election-rabbitmq rabbitmq-diagnostics ping`

### Database Connection Errors

**Check PostgreSQL:**
```bash
docker exec election-postgres psql -U postgres -d election_votes -c "SELECT 1;"
```

**Verify credentials:**
```bash
# In docker-compose.yml, ensure:
POSTGRES_PASSWORD: postgres  # matches in postgres and aggregator
```

### High Memory Usage

**Reduce batch size:**
```yaml
# In docker-compose.yml
environment:
  BATCH_SIZE: 50  # Reduce from 100
```

**Reduce connection pool:**
```yaml
environment:
  POSTGRES_MAX_CONNECTIONS: 5  # Reduce from 10
```

### Slow Performance

**Increase batch size:**
```yaml
environment:
  BATCH_SIZE: 500  # Increase from 100
  BATCH_TIMEOUT_SECONDS: 5.0  # Increase timeout
```

**Scale horizontally:**
```bash
docker-compose up -d --scale aggregator=3
```

---

## Production Deployment

### 1. Configure for Production

```bash
# Create production .env
cp .env.example .env.production

# Edit with production values
vim .env.production
```

**Important settings:**
- Use strong PostgreSQL password
- Use dedicated RabbitMQ credentials
- Set LOG_LEVEL=WARNING or ERROR
- Increase POSTGRES_MAX_CONNECTIONS for load
- Adjust BATCH_SIZE based on throughput needs

### 2. Build Production Image

```bash
docker build -t vote-aggregator:1.0.0 .
```

### 3. Deploy

**Docker Swarm:**
```bash
docker service create \
  --name vote-aggregator \
  --replicas 3 \
  --env-file .env.production \
  vote-aggregator:1.0.0
```

**Kubernetes:**
```bash
kubectl apply -f k8s/aggregator-deployment.yaml
```

### 4. Monitor

- Set up Prometheus alerts
- Configure Grafana dashboards
- Enable log aggregation (ELK, Loki)
- Set up health check endpoints

---

## Next Steps

1. **Read the full README.md** for detailed documentation
2. **Review ARCHITECTURE.md** to understand the system design
3. **Customize configuration** for your specific use case
4. **Set up monitoring** with Prometheus and Grafana
5. **Implement CI/CD** for automated deployments
6. **Add unit tests** for your custom logic
7. **Configure backups** for PostgreSQL data

---

## Support

For issues or questions:
1. Check logs: `docker-compose logs aggregator`
2. Review documentation: README.md, ARCHITECTURE.md
3. Verify configuration: .env file
4. Test components individually
5. Monitor metrics: http://localhost:8001/metrics

---

## Helpful Commands Cheatsheet

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# Restart aggregator
docker-compose restart aggregator

# View logs
docker-compose logs -f aggregator

# Check database
make check-db

# Check queue
make check-queue

# Publish test votes
make publish-test-votes

# View metrics
make metrics

# Scale aggregators
docker-compose up -d --scale aggregator=3

# Clean up
make clean
docker-compose down -v
```
