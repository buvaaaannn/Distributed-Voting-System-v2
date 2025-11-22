# Testing Quick Start Guide

Get up and running with the voting system tests in 5 minutes.

## Quick Setup

```bash
# 1. Install dependencies
cd tests/
pip install -r requirements.txt

# 2. Start services
cd ..
docker-compose up -d

# 3. Wait for services to be ready (30 seconds)
sleep 30

# 4. Run tests
cd tests/
pytest integration/ -v
```

## Common Commands

### Run All Tests
```bash
pytest integration/ -v
```

### Run Specific Test File
```bash
# Vote flow tests
pytest integration/test_vote_flow.py -v

# API tests
pytest integration/test_api.py -v

# Duplicate detection tests
pytest integration/test_duplicate_detection.py -v
```

### Run Single Test
```bash
pytest integration/test_vote_flow.py::TestVoteFlow::test_submit_valid_vote_and_verify_in_results -v
```

### Run With Coverage
```bash
pytest integration/ -v --cov --cov-report=html
open htmlcov/index.html
```

### Skip Slow Tests
```bash
pytest integration/ -v -m "not slow"
```

### Run Tests in Parallel (Faster)
```bash
pytest integration/ -v -n auto
```

## Load Testing

### Quick Load Test
```bash
# 1000 votes at 100/sec
python load_test.py --votes 1000 --rate 100
```

### Locust Web UI
```bash
locust -f load_test.py --host=http://localhost:8000
# Open http://localhost:8089 in browser
```

## Troubleshooting

### Services Not Running?
```bash
docker-compose ps
docker-compose logs
```

### Tests Failing?
```bash
# Clean slate
docker-compose down -v
docker-compose up -d
sleep 30
pytest integration/ -v
```

### Need Debug Output?
```bash
pytest integration/ -vv -s
```

## Expected Output

Successful test run:
```
integration/test_vote_flow.py::TestVoteFlow::test_submit_valid_vote ✓
integration/test_vote_flow.py::TestVoteFlow::test_submit_duplicate ✓
integration/test_api.py::TestVoteEndpoint::test_post_vote ✓
...
======================== 40 passed in 120.00s ========================
```

## Performance Targets

- Throughput: 500+ votes/second (local), 1000+ (production)
- Latency: p95 < 100ms
- Success Rate: >99.9%

## Next Steps

- Read [README.md](README.md) for detailed documentation
- Review [ARCHITECTURE.md](../ARCHITECTURE.md) for system design
- Check test files for examples

## Need Help?

1. Check service logs: `docker-compose logs [service]`
2. Verify services healthy: `curl http://localhost:8000/api/v1/health`
3. Review test output for specific error messages
4. See [README.md](README.md) Troubleshooting section
