# Deployment Checklist - Vote Aggregation Service

## Pre-Deployment

### 1. Code Review
- [ ] All Python files pass syntax validation
- [ ] Database schema reviewed and approved
- [ ] Configuration files reviewed
- [ ] Security review completed
- [ ] Dependencies are pinned versions

### 2. Testing
- [ ] Unit tests pass (if implemented)
- [ ] Integration tests pass
- [ ] Load testing completed
- [ ] Test vote publishing works
- [ ] Database operations validated

### 3. Infrastructure
- [ ] PostgreSQL 15+ available
- [ ] RabbitMQ 3.12+ available
- [ ] Network connectivity verified
- [ ] Firewall rules configured
- [ ] DNS entries created (if needed)

### 4. Configuration
- [ ] `.env` file created with production values
- [ ] Database credentials secured
- [ ] RabbitMQ credentials secured
- [ ] Batch size tuned for expected load
- [ ] Connection pool sized appropriately
- [ ] Log level set correctly

## Deployment Steps

### 1. Database Setup
```bash
# Initialize database
psql -h <POSTGRES_HOST> -U <POSTGRES_USER> -d election_votes -f init_db.sql

# Verify tables created
psql -h <POSTGRES_HOST> -U <POSTGRES_USER> -d election_votes -c "\dt"
```

- [ ] Database schema created
- [ ] Indexes created
- [ ] Views created
- [ ] Triggers created
- [ ] Sample data loaded (optional)

### 2. RabbitMQ Setup
```bash
# Create queue (if not auto-created)
rabbitmqadmin declare queue name=votes.aggregation durable=true
```

- [ ] Queue declared
- [ ] Permissions configured
- [ ] Management UI accessible

### 3. Build Container
```bash
# Build production image
docker build -t vote-aggregator:1.0.0 .

# Tag for registry
docker tag vote-aggregator:1.0.0 registry.example.com/vote-aggregator:1.0.0

# Push to registry
docker push registry.example.com/vote-aggregator:1.0.0
```

- [ ] Image built successfully
- [ ] Image tagged
- [ ] Image pushed to registry
- [ ] Image scanned for vulnerabilities

### 4. Deploy Service

**Option A: Docker**
```bash
docker run -d \
  --name vote-aggregator \
  --env-file .env.production \
  -p 8001:8001 \
  --restart unless-stopped \
  vote-aggregator:1.0.0
```

**Option B: Docker Compose**
```bash
docker-compose -f docker-compose.production.yml up -d
```

**Option C: Kubernetes**
```bash
kubectl apply -f k8s/aggregator-deployment.yaml
kubectl apply -f k8s/aggregator-service.yaml
```

- [ ] Service deployed
- [ ] Health check passing
- [ ] Logs accessible
- [ ] Metrics accessible

### 5. Verification
```bash
# Check service status
docker ps | grep aggregator
# or
kubectl get pods -l app=vote-aggregator

# Check logs
docker logs vote-aggregator
# or
kubectl logs -l app=vote-aggregator

# Check metrics
curl http://localhost:8001/metrics

# Test with sample vote
python test_publisher.py -n 10

# Verify database
psql -h <HOST> -U <USER> -d election_votes -c "SELECT * FROM vote_statistics;"
```

- [ ] Service running
- [ ] Connected to RabbitMQ
- [ ] Connected to PostgreSQL
- [ ] Metrics endpoint responding
- [ ] Test votes processed successfully
- [ ] Database updated correctly

## Post-Deployment

### 1. Monitoring Setup
- [ ] Prometheus scraping metrics
- [ ] Grafana dashboards configured
- [ ] Alerts configured
  - [ ] High error rate
  - [ ] Database connection failures
  - [ ] RabbitMQ connection failures
  - [ ] High processing latency
  - [ ] Queue depth threshold

### 2. Logging
- [ ] Logs aggregated (ELK, Loki, etc.)
- [ ] Log retention policy set
- [ ] Log rotation configured
- [ ] Error tracking enabled (Sentry, etc.)

### 3. Backup
- [ ] Database backup configured
- [ ] Backup retention policy set
- [ ] Backup restore tested
- [ ] Disaster recovery plan documented

### 4. Documentation
- [ ] Deployment documented
- [ ] Runbook created
- [ ] On-call procedures documented
- [ ] Escalation contacts listed

### 5. Performance Baseline
- [ ] Initial metrics captured
- [ ] Performance baselines established
- [ ] Capacity planning completed
- [ ] Load testing results documented

## Scaling Checklist

### Horizontal Scaling
```bash
# Docker Compose
docker-compose up -d --scale aggregator=3

# Kubernetes
kubectl scale deployment vote-aggregator --replicas=3
```

- [ ] Multiple instances running
- [ ] Load distributed evenly
- [ ] No duplicate processing
- [ ] Metrics from all instances

### Vertical Scaling
- [ ] CPU/memory limits adjusted
- [ ] Connection pool size increased
- [ ] Batch size tuned
- [ ] Prefetch count adjusted

## Rollback Plan

### 1. Preparation
- [ ] Previous version tagged
- [ ] Rollback procedure documented
- [ ] Database migration reversible (if applicable)

### 2. Rollback Steps
```bash
# Stop current version
docker stop vote-aggregator

# Start previous version
docker run -d \
  --name vote-aggregator \
  --env-file .env.production \
  -p 8001:8001 \
  vote-aggregator:0.9.0

# Verify
curl http://localhost:8001/metrics
```

- [ ] Service stopped gracefully
- [ ] Previous version started
- [ ] Connections restored
- [ ] Processing resumed
- [ ] No data loss

## Security Checklist

### 1. Credentials
- [ ] Database password strong and unique
- [ ] RabbitMQ password strong and unique
- [ ] Credentials stored in secrets manager
- [ ] No credentials in code or logs

### 2. Network
- [ ] Database not exposed to internet
- [ ] RabbitMQ not exposed to internet
- [ ] Metrics endpoint firewalled (if sensitive)
- [ ] TLS/SSL enabled for connections

### 3. Access Control
- [ ] Database user has minimal permissions
- [ ] RabbitMQ user has minimal permissions
- [ ] Container runs as non-root
- [ ] File permissions correct

### 4. Compliance
- [ ] Data retention policy compliant
- [ ] Audit logging enabled
- [ ] PII handling reviewed
- [ ] GDPR compliance verified (if applicable)

## Maintenance Schedule

### Daily
- [ ] Check error logs
- [ ] Monitor queue depth
- [ ] Review metrics dashboard

### Weekly
- [ ] Review performance trends
- [ ] Check disk usage
- [ ] Verify backups

### Monthly
- [ ] Security updates
- [ ] Dependency updates
- [ ] Capacity planning review
- [ ] Performance optimization

### Quarterly
- [ ] Disaster recovery test
- [ ] Security audit
- [ ] Documentation update
- [ ] Architecture review

## Troubleshooting Quick Reference

### Service Won't Start
1. Check logs: `docker logs vote-aggregator`
2. Verify environment variables
3. Test database connection
4. Test RabbitMQ connection

### High Error Rate
1. Check database health
2. Check RabbitMQ health
3. Review error logs
4. Check for malformed messages

### High Latency
1. Check batch size configuration
2. Monitor database connection pool
3. Check RabbitMQ prefetch count
4. Review system resources

### Memory Issues
1. Reduce batch size
2. Reduce connection pool size
3. Check for memory leaks
4. Review log buffer size

## Contact Information

**On-Call Support:**
- Primary: [Name/Contact]
- Secondary: [Name/Contact]
- Escalation: [Name/Contact]

**Infrastructure:**
- Database Admin: [Contact]
- DevOps Team: [Contact]
- Security Team: [Contact]

**Vendor Support:**
- PostgreSQL: [Support Link]
- RabbitMQ: [Support Link]
- Cloud Provider: [Support Link]

---

## Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Developer | | | |
| DevOps | | | |
| Security | | | |
| Manager | | | |

---

**Deployment Date:** _____________

**Deployment Version:** 1.0.0

**Deployment Notes:**
_________________________________________________
_________________________________________________
_________________________________________________
