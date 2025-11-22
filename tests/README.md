# Voting System - Test Suite

Comprehensive integration and load testing suite for the distributed voting system.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Running Tests](#running-tests)
- [Test Coverage](#test-coverage)
- [Load Testing](#load-testing)
- [CI/CD Integration](#cicd-integration)
- [Troubleshooting](#troubleshooting)

---

## Overview

This test suite includes:

1. **Integration Tests** - End-to-end testing of the complete voting pipeline
2. **API Tests** - REST API endpoint validation
3. **Duplicate Detection Tests** - Vote deduplication logic verification
4. **Load Tests** - Performance and scalability testing

### Test Statistics

- **Total Integration Tests**: 40+
- **Test Coverage Target**: >80%
- **Performance Targets**:
  - Throughput: 1000 votes/second
  - Latency: p95 < 100ms
  - Success Rate: >99.9%

---

## Prerequisites

### Required Services

The integration tests require the full docker-compose stack running:

- **Ingestion API** (FastAPI) - Port 8000
- **RabbitMQ** - Port 5672 (management: 15672)
- **Redis** - Port 6379
- **PostgreSQL** - Port 5432
- **Validation Workers**
- **Aggregation Service**

### Software Requirements

- Python 3.11+
- Docker & Docker Compose
- pip (Python package manager)

---

## Installation

### 1. Install Test Dependencies

```bash
cd tests/
pip install -r requirements.txt
```

### 2. Start Docker Services

```bash
# From project root
docker-compose up -d

# Verify services are running
docker-compose ps
```

### 3. Load Sample Hashes (for testing)

```bash
# From project root
python scripts/load_hashes_to_redis.py --sample
```

---

## Running Tests

### Run All Integration Tests

```bash
# From tests/ directory
pytest integration/ -v

# With coverage report
pytest integration/ -v --cov --cov-report=html
```

### Run Specific Test Files

```bash
# Vote flow tests only
pytest integration/test_vote_flow.py -v

# API endpoint tests only
pytest integration/test_api.py -v

# Duplicate detection tests only
pytest integration/test_duplicate_detection.py -v
```

### Run Specific Test Cases

```bash
# Run a single test by name
pytest integration/test_vote_flow.py::TestVoteFlow::test_submit_valid_vote_and_verify_in_results -v

# Run tests matching a pattern
pytest integration/ -k "duplicate" -v
```

### Run Tests with Markers

```bash
# Run only tests marked as 'docker' (require docker stack)
pytest integration/ -m docker -v

# Skip slow tests
pytest integration/ -m "not slow" -v

# Run only load tests
pytest integration/ -m load -v
```

### Parallel Test Execution

```bash
# Run tests in parallel (faster execution)
pytest integration/ -n auto -v
```

### Generate HTML Report

```bash
# Generate HTML test report
pytest integration/ -v --html=report.html --self-contained-html
```

---

## Test Coverage

### View Coverage Report

```bash
# Run tests with coverage
pytest integration/ --cov=../services --cov-report=html

# Open HTML report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### Coverage Targets

| Component | Target Coverage |
|-----------|----------------|
| Ingestion API | >85% |
| Validation Worker | >90% |
| Aggregation Service | >85% |
| Overall System | >80% |

---

## Load Testing

### Using Custom Async Load Test

```bash
# From tests/ directory

# Basic load test: 1000 votes at 100 votes/sec
python load_test.py --votes 1000 --rate 100

# High load: 10000 votes at 500 votes/sec
python load_test.py --votes 10000 --rate 500

# Time-limited test: run for 60 seconds
python load_test.py --votes 100000 --rate 1000 --duration 60

# Custom host
python load_test.py --votes 1000 --rate 100 --host http://api.voting.example.com
```

### Using Locust (Web UI + Distributed Testing)

```bash
# Start Locust web UI
locust -f load_test.py --host=http://localhost:8000

# Open browser to http://localhost:8089
# Configure:
#   - Number of users: 100
#   - Spawn rate: 10 users/second
#   - Host: http://localhost:8000
```

#### Distributed Load Testing with Locust

```bash
# Master node
locust -f load_test.py --master --host=http://localhost:8000

# Worker nodes (run on multiple machines)
locust -f load_test.py --worker --master-host=<master-ip>
```

### Load Test Scenarios

#### Scenario 1: Peak Load (Election Day)
```bash
# Simulate 8M votes in 24 hours (avg 92 votes/sec, peak 1000 votes/sec)
python load_test.py --votes 100000 --rate 1000 --duration 300
```

#### Scenario 2: Sustained Load
```bash
# Verify system handles sustained 500 votes/sec
python load_test.py --votes 30000 --rate 500 --duration 60
```

#### Scenario 3: Stress Test
```bash
# Push system to limits
python load_test.py --votes 50000 --rate 2000 --duration 30
```

### Interpreting Results

The load test generates a detailed report:

```
📊 LOAD TEST RESULTS
======================================================================

⏱️  Duration: 60.00 seconds
📈 Total Requests: 30,000
✅ Successful: 29,950 (99.83%)
❌ Failed: 50 (0.17%)

🚀 Throughput:
   - Requests/sec: 500.00
   - Votes/sec: 500.00

⏲️  Latency (ms):
   - Min: 12.50
   - Max: 450.00
   - Mean: 45.30
   - Median (p50): 42.10
   - p95: 98.50
   - p99: 145.20

🎯 Performance Assessment:
   ✅ Throughput: GOOD (≥500 req/s)
   ✅ Latency (p95): EXCELLENT (<100ms)
   ✅ Success Rate: EXCELLENT (≥99.9%)
```

**Thresholds:**
- **Throughput**: EXCELLENT ≥1000, GOOD ≥500
- **Latency (p95)**: EXCELLENT <100ms, GOOD <200ms
- **Success Rate**: EXCELLENT ≥99.9%, GOOD ≥99%

---

## Test Structure

### Directory Layout

```
tests/
├── integration/
│   ├── conftest.py                    # Pytest fixtures
│   ├── test_vote_flow.py              # End-to-end vote flow tests
│   ├── test_api.py                    # API endpoint tests
│   └── test_duplicate_detection.py    # Duplicate handling tests
├── unit/                              # Unit tests (separate)
├── load_test.py                       # Load testing script
├── requirements.txt                   # Test dependencies
└── README.md                          # This file
```

### Key Test Files

#### `integration/conftest.py`
Pytest fixtures for test setup/teardown:
- `docker_compose` - Start/stop docker stack
- `api_client` - HTTP client for API calls
- `redis_client` - Redis connection
- `postgres_client` - PostgreSQL connection
- `clear_databases` - Clean test data
- `sample_votes` - Test vote data
- `load_sample_hashes` - Populate Redis with valid hashes

#### `integration/test_vote_flow.py`
End-to-end vote flow tests:
- Submit valid vote → verify in results
- Submit duplicate vote → verify rejection
- Submit invalid hash → verify rejection
- Submit 100 votes → verify all counted
- Submit invalid format → verify 400 error
- Concurrent vote submission
- Multiple laws isolation

#### `integration/test_api.py`
API endpoint tests:
- POST /api/v1/vote (valid/invalid data)
- GET /api/v1/results/{law_id}
- GET /api/v1/health
- Rate limiting
- Concurrent requests
- Error handling

#### `integration/test_duplicate_detection.py`
Duplicate detection tests:
- Same vote twice → count once
- Same vote 5 times → attempt counter = 5
- Duplicate logged in audit table
- Vote change not allowed
- Case sensitivity
- Concurrent duplicate submissions

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Integration Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd tests/
          pip install -r requirements.txt

      - name: Start services
        run: docker-compose up -d

      - name: Wait for services
        run: sleep 30

      - name: Run integration tests
        run: |
          cd tests/
          pytest integration/ -v --cov --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./tests/coverage.xml

      - name: Stop services
        run: docker-compose down -v
```

### GitLab CI Example

```yaml
test:
  image: python:3.11
  services:
    - docker:dind
  before_script:
    - pip install -r tests/requirements.txt
    - docker-compose up -d
    - sleep 30
  script:
    - cd tests/
    - pytest integration/ -v --cov --cov-report=term
  after_script:
    - docker-compose down -v
```

---

## Troubleshooting

### Common Issues

#### 1. Services Not Starting

**Problem**: Tests fail with connection errors

**Solution**:
```bash
# Check if services are running
docker-compose ps

# Check service logs
docker-compose logs ingestion-api
docker-compose logs validation-worker

# Restart services
docker-compose restart
```

#### 2. Redis Doesn't Have Valid Hashes

**Problem**: All votes rejected as invalid hash

**Solution**:
```bash
# Load sample hashes
python scripts/load_hashes_to_redis.py --sample

# Verify hashes loaded
docker-compose exec redis redis-cli SCARD valid_hashes
```

#### 3. Tests Timing Out

**Problem**: Tests hang or timeout

**Solution**:
```bash
# Increase timeout in pytest.ini
[pytest]
timeout = 300

# Or run with timeout flag
pytest integration/ --timeout=300
```

#### 4. Database Connection Errors

**Problem**: PostgreSQL connection refused

**Solution**:
```bash
# Check PostgreSQL is running
docker-compose exec postgres pg_isready

# Check database exists
docker-compose exec postgres psql -U election_user -d election_db -c "\l"

# Recreate database
docker-compose down -v
docker-compose up -d
```

#### 5. Port Conflicts

**Problem**: Docker services won't start due to port conflicts

**Solution**:
```bash
# Check what's using the ports
lsof -i :8000  # API
lsof -i :5672  # RabbitMQ
lsof -i :6379  # Redis
lsof -i :5432  # PostgreSQL

# Stop conflicting services or change ports in docker-compose.yml
```

### Debug Mode

Run tests with verbose output and debug logging:

```bash
# Pytest verbose mode
pytest integration/ -vv

# Show print statements
pytest integration/ -v -s

# Show fixtures used
pytest integration/ --fixtures

# Debug specific test
pytest integration/test_vote_flow.py::test_name -vv -s
```

### Clean Slate

If tests are failing unexpectedly, reset everything:

```bash
# Stop and remove all containers, volumes, networks
docker-compose down -v

# Remove test artifacts
rm -rf htmlcov/ .coverage .pytest_cache/

# Restart fresh
docker-compose up -d
sleep 30

# Run tests
pytest integration/ -v
```

---

## Best Practices

### Writing New Tests

1. **Use fixtures** for setup/teardown
2. **Clear databases** before each test
3. **Use unique test data** to avoid conflicts
4. **Test both success and failure** cases
5. **Add descriptive docstrings**
6. **Use appropriate markers** (@pytest.mark.docker, @pytest.mark.slow)

### Example Test Template

```python
@pytest.mark.docker
@pytest.mark.asyncio
async def test_my_feature(
    api_client: httpx.AsyncClient,
    clear_databases,
    load_sample_hashes,
    wait_for_processing
):
    """Test description explaining what and why.

    Flow:
    1. Setup
    2. Action
    3. Assertion
    """
    # Arrange
    test_data = {...}

    # Act
    response = await api_client.post("/api/v1/vote", json=test_data)

    # Assert
    assert response.status_code == 202
    wait_for_processing()
    # ... more assertions
```

---

## Performance Benchmarks

### Current System Performance (Local Docker)

| Metric | Value |
|--------|-------|
| Peak Throughput | ~150 votes/sec |
| p95 Latency | 80ms |
| Success Rate | 99.5% |

### Production Targets (Kubernetes)

| Metric | Target |
|--------|--------|
| Peak Throughput | 1000 votes/sec |
| p95 Latency | <100ms |
| Success Rate | >99.9% |
| Availability | 99.9% |

---

## Additional Resources

- [System Architecture](../ARCHITECTURE.md)
- [API Documentation](../services/ingestion_api/README.md)
- [Deployment Guide](../k8s/README.md)
- [pytest Documentation](https://docs.pytest.org/)
- [Locust Documentation](https://docs.locust.io/)

---

## Support

For issues or questions:

1. Check the [Troubleshooting](#troubleshooting) section
2. Review test output and logs
3. Check service health: `docker-compose ps` and `docker-compose logs`
4. Contact the development team

---

## License

See main project LICENSE file.
