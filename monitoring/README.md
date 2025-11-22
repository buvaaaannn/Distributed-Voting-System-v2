# Election Voting System - Monitoring Guide

This directory contains the complete monitoring stack configuration for the election voting system, including Prometheus for metrics collection and Grafana for visualization.

## Architecture Overview

The monitoring stack consists of:
- **Prometheus**: Time-series database and alerting engine
- **Grafana**: Visualization and dashboard platform
- **Exporters**: Specialized exporters for Redis, PostgreSQL, and RabbitMQ

## Quick Start

### Accessing Dashboards

1. **Grafana**: http://localhost:3000
   - Default credentials: admin/admin (change on first login)
   - Main dashboard: "Election Voting System - Overview"

2. **Prometheus**: http://localhost:9090
   - Query interface and alert status

### Directory Structure

```
monitoring/
├── prometheus/
│   ├── prometheus.yml      # Prometheus configuration
│   └── alerts.yml          # Alert rules
├── grafana/
│   ├── dashboards/
│   │   └── voting_overview.json    # Main dashboard
│   └── provisioning/
│       ├── datasources/
│       │   └── prometheus.yml      # Datasource config
│       └── dashboards/
│           └── dashboards.yml      # Dashboard provisioning
└── README.md
```

## Metrics Reference

### Application Metrics

#### Ingestion API
- `votes_received_total`: Counter of votes received
- `votes_by_law_total`: Counter of votes per law/referendum
- `http_requests_total`: HTTP requests by status code
- `http_request_duration_seconds`: Request latency histogram
- `http_request_size_bytes`: Request size histogram
- `http_response_size_bytes`: Response size histogram

#### Validation Workers
- `votes_validation_processed_total`: Counter of validated votes
- `votes_validation_status_total`: Counter by validation status (valid/invalid)
- `votes_duplicate_total`: Counter of duplicate attempts
- `votes_validation_failed_total`: Counter of validation failures
- `validation_duration_seconds`: Validation processing time histogram

#### Aggregation Service
- `votes_aggregated_total`: Counter of aggregated votes
- `aggregation_duration_seconds`: Aggregation processing time histogram
- `aggregation_lag_seconds`: Time lag behind real-time

### Infrastructure Metrics

#### RabbitMQ
- `rabbitmq_queue_messages`: Messages in queue
- `rabbitmq_queue_messages_ready`: Messages ready for delivery
- `rabbitmq_queue_messages_unacknowledged`: Messages pending acknowledgment
- `rabbitmq_queue_messages_published_total`: Messages published to queue
- `rabbitmq_queue_messages_consumed_total`: Messages consumed from queue
- `rabbitmq_disk_space_available_bytes`: Available disk space

#### Redis
- `redis_memory_used_bytes`: Memory usage
- `redis_memory_max_bytes`: Maximum memory limit
- `redis_connected_clients`: Number of connected clients
- `redis_keyspace_hits_total`: Cache hits
- `redis_keyspace_misses_total`: Cache misses
- `redis_evicted_keys_total`: Evicted keys

#### PostgreSQL
- `pg_stat_database_numbackends`: Active connections
- `pg_settings_max_connections`: Maximum connections allowed
- `pg_stat_database_xact_commit`: Committed transactions
- `pg_stat_database_xact_rollback`: Rolled back transactions
- `pg_stat_database_blks_read`: Disk blocks read
- `pg_stat_database_blks_hit`: Disk blocks from cache

## Dashboard Panels

### Voting Overview Dashboard

1. **Votes Per Second**
   - Time series showing vote ingestion rate
   - Helps identify traffic patterns and peak loads

2. **Total Votes by Law**
   - Gauge showing cumulative votes per law/referendum
   - Color-coded by volume thresholds

3. **Validation Status Breakdown**
   - Pie chart showing distribution of valid/invalid/duplicate votes
   - Quick health check for data quality

4. **Queue Depth**
   - Time series of message queue depths
   - Critical for identifying backlog and processing issues

5. **API Latency (p50/p95/p99)**
   - Percentile latencies for API requests
   - p95 threshold: 200ms (warning), 500ms (critical)

6. **Duplicate Attempt Rate**
   - Percentage of duplicate vote attempts
   - Threshold: 5% (warning), 15% (critical)

7. **Active Workers**
   - Gauge showing number of running validation workers
   - Minimum required: 2 workers

8. **Redis Memory Usage**
   - Gauge showing Redis memory consumption
   - Threshold: 80% (warning), 95% (critical)

9. **Database Connections**
   - Gauge showing DB connection pool utilization
   - Threshold: 80% (warning), 90% (critical)

10. **HTTP Requests by Status Code**
    - Stacked area chart of HTTP status codes
    - Color-coded: 2xx (green), 4xx (orange), 5xx (red)

11. **Validation Processing Rate**
    - Rate of vote validation per worker
    - Expected: >100 votes/sec per worker

## Alert Rules

### Critical Alerts (Immediate Action Required)

1. **IngestionAPIDown**
   - Trigger: API unreachable for 1 minute
   - Impact: No votes can be received
   - Action: Check API service, logs, and infrastructure

2. **ValidationWorkerDown**
   - Trigger: Less than 2 workers running for 2 minutes
   - Impact: Reduced processing capacity
   - Action: Restart workers, check for crashes

3. **RabbitMQDown**
   - Trigger: RabbitMQ unreachable for 1 minute
   - Impact: Vote processing halted
   - Action: Restart RabbitMQ, check disk space and memory

4. **RedisDown**
   - Trigger: Redis unreachable for 1 minute
   - Impact: Deduplication disabled, duplicate votes may be accepted
   - Action: Restart Redis, check persistence files

5. **PostgresDown**
   - Trigger: PostgreSQL unreachable for 1 minute
   - Impact: Vote persistence stopped
   - Action: Restart database, check logs and disk space

6. **CriticalValidationQueueDepth**
   - Trigger: >50,000 messages in validation queue for 2 minutes
   - Impact: System overwhelmed, significant lag
   - Action: Scale up workers, check for processing issues

7. **CriticalDuplicateRate**
   - Trigger: >15% duplicate rate for 5 minutes
   - Impact: Possible attack or system compromise
   - Action: Enable rate limiting, investigate traffic source

8. **APICriticalLatency**
   - Trigger: p95 latency >500ms for 2 minutes
   - Impact: Severely degraded user experience
   - Action: Check database performance, scale API instances

9. **CriticalAPIErrorRate**
   - Trigger: >15% error rate for 2 minutes
   - Impact: Most requests failing
   - Action: Check logs, database connectivity, dependencies

10. **CriticalRedisMemoryUsage**
    - Trigger: >95% memory usage for 2 minutes
    - Impact: Evictions occurring, deduplication may fail
    - Action: Increase memory limit or implement eviction policy

11. **RabbitMQDiskSpaceLow**
    - Trigger: <1GB available disk space for 5 minutes
    - Impact: Message flow blocked
    - Action: Clear old messages, increase disk space

12. **QueueConsumerStall**
    - Trigger: Messages in queue but no consumption for 5 minutes
    - Impact: Processing stopped despite available work
    - Action: Restart workers, check for deadlocks

### Warning Alerts (Action Recommended)

1. **HighValidationQueueDepth**
   - Trigger: >10,000 messages for 5 minutes
   - Action: Monitor closely, prepare to scale workers

2. **HighDuplicateRate**
   - Trigger: >5% duplicate rate for 10 minutes
   - Action: Investigate traffic patterns, check for misconfiguration

3. **APIHighLatency**
   - Trigger: p95 latency >200ms for 5 minutes
   - Action: Monitor performance, consider optimization

4. **AggregationServiceDown**
   - Trigger: Service unreachable for 2 minutes
   - Impact: Real-time results unavailable (votes still processed)
   - Action: Restart service, not critical for vote processing

5. **HighAPIErrorRate**
   - Trigger: >5% error rate for 5 minutes
   - Action: Check logs for error patterns

6. **HighValidationErrorRate**
   - Trigger: >10% validation failures for 5 minutes
   - Action: Check validation rules, inspect failing votes

7. **HighRedisMemoryUsage**
   - Trigger: >80% memory usage for 5 minutes
   - Action: Monitor memory trend, plan capacity increase

8. **HighDatabaseConnections**
   - Trigger: >80% of max connections for 5 minutes
   - Action: Check for connection leaks, increase pool size

9. **SlowValidationProcessing**
   - Trigger: <100 votes/sec for 10 minutes
   - Action: Check worker health, database performance

## Troubleshooting Guide

### High Queue Depth

**Symptoms**: Messages accumulating in validation or aggregation queues

**Possible Causes**:
- Insufficient worker capacity
- Worker crashes or deadlocks
- Database performance issues
- Network connectivity problems

**Diagnostic Steps**:
1. Check worker health: `docker ps | grep validation-worker`
2. Check worker logs: `docker logs validation-worker-1`
3. Monitor validation rate: Check "Validation Processing Rate" panel
4. Check database performance: Look at connection count and query times

**Solutions**:
- Scale up workers: `docker-compose up -d --scale validation-worker=8`
- Restart stuck workers: `docker-compose restart validation-worker`
- Optimize database queries or add indexes
- Check network latency between services

### High Duplicate Rate

**Symptoms**: Duplicate attempt rate >5%

**Possible Causes**:
- Double-click submissions from frontend
- API retry logic issues
- Load balancer misconfiguration
- Malicious activity

**Diagnostic Steps**:
1. Check voter ID patterns in duplicates
2. Review API access logs for suspicious patterns
3. Check frontend code for double-submit prevention
4. Monitor duplicate rate by endpoint

**Solutions**:
- Implement frontend debouncing
- Add idempotency tokens to API
- Enable rate limiting per voter ID
- Block suspicious IP addresses

### High API Latency

**Symptoms**: p95 latency >200ms

**Possible Causes**:
- Database slow queries
- High CPU utilization
- Network latency
- Insufficient API instances
- Cache misses

**Diagnostic Steps**:
1. Check database query performance: `SELECT * FROM pg_stat_statements ORDER BY mean_time DESC`
2. Monitor CPU usage: Check node exporter metrics
3. Review API logs for slow requests
4. Check Redis hit rate: `redis_keyspace_hits_total / (redis_keyspace_hits_total + redis_keyspace_misses_total)`

**Solutions**:
- Add database indexes
- Optimize slow queries
- Scale API horizontally: `docker-compose up -d --scale ingestion-api=4`
- Increase cache TTL
- Enable connection pooling

### Worker Crashes

**Symptoms**: Active workers count dropping, workers restarting

**Possible Causes**:
- Out of memory (OOM)
- Unhandled exceptions
- Message processing failures
- Resource exhaustion

**Diagnostic Steps**:
1. Check worker logs: `docker logs --tail 100 validation-worker-1`
2. Monitor memory usage: Check container stats
3. Look for error patterns in logs
4. Check RabbitMQ message redelivery count

**Solutions**:
- Increase worker memory limits
- Fix application bugs causing crashes
- Add error handling for malformed messages
- Implement graceful degradation
- Add message dead-letter queue

### Redis Memory Issues

**Symptoms**: Redis memory usage >80%, evictions occurring

**Possible Causes**:
- Deduplication window too long
- TTL not set on keys
- Memory limit too low
- Key accumulation

**Diagnostic Steps**:
1. Check key count: `redis-cli DBSIZE`
2. Sample keys: `redis-cli --scan --pattern 'vote:*' | head`
3. Check TTL: `redis-cli TTL vote:<voter_id>:<law_id>`
4. Monitor eviction rate: `redis_evicted_keys_total`

**Solutions**:
- Reduce deduplication window (e.g., 24h → 12h)
- Ensure all keys have TTL set
- Increase Redis memory limit
- Implement LRU eviction policy
- Use Redis cluster for scaling

### Database Connection Pool Exhausted

**Symptoms**: Connection usage >80%, connection timeout errors

**Possible Causes**:
- Connection leaks
- Long-running transactions
- Insufficient pool size
- Database performance issues

**Diagnostic Steps**:
1. Check active queries: `SELECT * FROM pg_stat_activity`
2. Look for long-running transactions: `SELECT * FROM pg_stat_activity WHERE state = 'active' AND xact_start < NOW() - INTERVAL '5 minutes'`
3. Monitor connection lifetime
4. Check for idle connections: `SELECT * FROM pg_stat_activity WHERE state = 'idle'`

**Solutions**:
- Fix connection leaks in code
- Increase connection pool size
- Set connection timeout limits
- Kill long-running queries
- Optimize database performance

## Performance Tuning

### Scaling Guidelines

**When to scale**:
- Queue depth consistently >10,000 messages
- API latency p95 >200ms
- Worker CPU usage >80%
- Database connection pool >80% utilized

**Scaling strategies**:
1. **Horizontal scaling** (preferred):
   - API: `docker-compose up -d --scale ingestion-api=4`
   - Workers: `docker-compose up -d --scale validation-worker=8`

2. **Vertical scaling**:
   - Increase container memory/CPU limits
   - Upgrade database instance size

3. **Database scaling**:
   - Add read replicas for aggregation queries
   - Implement connection pooling (PgBouncer)
   - Partition tables by time or law_id

### Capacity Planning

**Expected throughput**:
- Ingestion API: 1,000 votes/sec per instance
- Validation Worker: 100-200 votes/sec per instance
- Database: 5,000 writes/sec (with proper indexes)

**Resource recommendations**:
- Minimum: 4 validation workers, 2 API instances
- Medium load (1,000 votes/sec): 8 workers, 4 API instances
- High load (5,000 votes/sec): 16 workers, 8 API instances

## Custom Queries

### Useful PromQL Queries

```promql
# Vote ingestion rate over last hour
rate(votes_received_total[1h])

# Validation success rate
rate(votes_validation_status_total{status="valid"}[5m]) / rate(votes_validation_processed_total[5m]) * 100

# Queue processing lag
rabbitmq_queue_messages / rate(rabbitmq_queue_messages_consumed_total[5m])

# Redis cache hit rate
rate(redis_keyspace_hits_total[5m]) / (rate(redis_keyspace_hits_total[5m]) + rate(redis_keyspace_misses_total[5m])) * 100

# Database transaction rate
rate(pg_stat_database_xact_commit[5m])

# Top laws by vote count
topk(10, votes_by_law_total)

# Error rate by endpoint
rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) * 100
```

## Integration with Alertmanager

To receive alerts via email, Slack, or PagerDuty, configure Alertmanager:

```yaml
# alertmanager.yml
route:
  receiver: 'default'
  group_by: ['alertname', 'cluster', 'service']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  routes:
    - match:
        severity: critical
      receiver: 'pagerduty'
    - match:
        severity: warning
      receiver: 'slack'

receivers:
  - name: 'default'
    email_configs:
      - to: 'ops-team@example.com'

  - name: 'slack'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/XXX'
        channel: '#alerts'

  - name: 'pagerduty'
    pagerduty_configs:
      - service_key: 'YOUR_SERVICE_KEY'
```

## Backup and Retention

**Prometheus data retention**:
- Default: 15 days
- Adjust in prometheus.yml: `--storage.tsdb.retention.time=30d`

**Grafana dashboard backup**:
- Dashboards stored in JSON format
- Version controlled in git
- Auto-provisioned on startup

## Additional Resources

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [RabbitMQ Monitoring](https://www.rabbitmq.com/monitoring.html)
- [Redis Monitoring](https://redis.io/topics/monitoring)
- [PostgreSQL Statistics](https://www.postgresql.org/docs/current/monitoring-stats.html)

## Support

For monitoring issues or questions:
1. Check Prometheus targets: http://localhost:9090/targets
2. Review Grafana datasource status
3. Verify exporter connectivity
4. Check service logs: `docker-compose logs <service-name>`
