# Distributed Voting System v2

**Author:** David Marleau
**License:** MIT License
**Status:** 🚧 **DEMO VERSION - FUNCTIONAL BUT INCOMPLETE** 🚧

This is a **functional demonstration** of a production-grade distributed voting system designed to handle 8 million concurrent voters across Canada. While the core architecture and features work correctly, this project is **not production-ready** and requires additional development for real-world deployment.

## Overview

Distributed voting system supporting both law voting (referendums) and electoral elections with ranked-choice voting capabilities.

## Features

- **Law Voting**: Direct democracy referendums (Oui/Non)
- **Electoral Elections**: Regional representative elections
  - Single-choice and Ranked-choice voting support
  - Multi-candidate races with party affiliations
  - Real-time results tracking
  - Election timing controls (start/end datetime)
- **High Performance**: RabbitMQ queue buffering for 8M+ concurrent users
- **Security**: Offline hash validation, no PII storage
- **Scalable**: Kubernetes-ready microservices architecture
- **Monitoring**: Prometheus + Grafana dashboards

## Quick Start

### Ultra-Fast Start (Single Command)

```bash
./quick-start.sh
```

This script automatically starts all services in 20 seconds! 🚀

### Manual Start

#### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- kubectl (for production deployment)

#### Steps

1. **Start Docker services**:
```bash
docker-compose up -d
```

2. **Start the monitor dashboard**:
```bash
python3 monitor_dashboard/server.py &
```

3. **Start the voting interface**:
```bash
cd demo_ui && python3 app.py &
```

4. **Access the services**:
- **Voting UI**: http://localhost:3000
  - Law voting tab
  - Election voting tab
  - Results pages
- **Admin Panel**: http://localhost:8501
  - Create elections
  - Configure voting methods (single-choice / ranked-choice)
  - Set election timing
  - Manage candidates
- **Monitor Dashboard**: http://localhost:4000/monitor.html
  - Live election results (auto-refresh every 5s)
  - **📊 "All Regions" aggregation** - National totals by default
  - Region-specific breakdowns available
  - Law voting results table
  - Vote statistics
- **Vote API**: http://localhost:8000
- **RabbitMQ Management**: http://localhost:15672 (guest/guest)
- **Grafana**: http://localhost:3001 (admin/admin)
- **Prometheus**: http://localhost:9090

### Submit Test Votes

**Law Vote:**
```bash
curl -X POST http://localhost:8000/api/v1/vote \
  -H "Content-Type: application/json" \
  -d '{
    "nas": "123456789",
    "code": "ABC123",
    "law_id": "L2025-001",
    "vote": "oui"
  }'
```

**Election Vote:**
```bash
curl -X POST http://localhost:8000/api/v1/elections/vote \
  -H "Content-Type: application/json" \
  -d '{
    "nas": "123456789",
    "code": "ABC123",
    "election_id": 1,
    "region_id": 1,
    "candidate_id": 1,
    "voting_method": "single_choice"
  }'
```

### View Results

**Law Results:**
```bash
curl http://localhost:8000/api/v1/results/L2025-001
```

**Election Results:**
```bash
curl http://localhost:8000/api/v1/elections/1/regions/1/results
```

## Project Structure

```
electionscriptanalyse/
├── services/                    # Microservices
│   ├── ingestion_api/          # Vote submission API (FastAPI)
│   ├── validation_worker/      # Hash validation & deduplication
│   ├── aggregation/            # Vote counting & aggregation
│   └── shared/                 # Shared utilities & models
├── demo_ui/                     # Web-based voting interface
│   └── app.py                  # Flask app with law & election voting
├── tests/                       # Test suites
│   ├── voting_test_gui.py      # Streamlit admin panel
│   ├── load_test.py            # 8M vote load testing
│   ├── test_election_simple.py # Direct DB election test (30k votes)
│   └── integration/            # Integration tests
├── monitor_dashboard/           # Real-time results dashboard
│   ├── server.py               # Python HTTP server
│   └── monitor.html            # Live election results UI
├── scripts/                     # Utility scripts
│   ├── preload_test_hashes.py  # Generate 8M test vote credentials
│   └── load_hashes_to_redis.py # Load hash database
├── monitoring/                  # Prometheus & Grafana
│   ├── prometheus/
│   └── grafana/
├── test_results/               # Load test results (organized)
├── data/                       # Data directory
│   └── init_db.sql            # Database schema & sample data
├── docker-compose.yml          # Local development stack
├── ARCHITECTURE.md             # System architecture docs
├── QUICKSTART.md               # Getting started guide
└── README.md                   # This file
```

## Architecture

See [ARCHITECTURE.md](./ARCHITECTURE.md) for detailed system design.

**Key Components:**
- **Ingestion API**: FastAPI vote submission with law & election support
- **RabbitMQ**: Message queue buffer for handling traffic spikes (8M users)
- **Validation Workers**: Scalable workers for hash validation
- **Redis**: Fast hash lookup (8M hashes) and duplicate detection
- **PostgreSQL**: Persistent storage for law results, elections, candidates
- **Monitoring**: Prometheus + Grafana dashboards

**Vote Flow:**
```
Voter → Ingestion API (FastAPI)
          ↓
       RabbitMQ Queue (BUFFER) ← Handles burst traffic
          ↓
     Validation Workers (Scalable)
          ↓
       PostgreSQL + Redis
```

## Election System

### Database Schema

**Elections Table:**
- `election_code`, `election_name`, `election_type`
- `start_datetime`, `end_datetime` - Voting window control
- `voting_method` - `single_choice` or `ranked_choice`
- `status` - `draft`, `active`, `completed`

**Candidates Table:**
- Links to elections, regions, and political parties
- `first_name`, `last_name`, `bio`

**Election Results:**
- Real-time aggregation in `election_results` table
- Vote counts and percentages per candidate/region

### Features Implemented

- ✅ Ranked-choice voting toggle in Admin Panel
- ✅ Election timing (start/end datetime)
- ✅ Vote cutoff validation (no votes after deadline)
- ✅ Election results on monitor dashboard with **"All Regions"** aggregation
- ✅ National election totals (automatic aggregation across all regions)
- ✅ Region-specific result breakdowns
- ✅ RabbitMQ pipeline: API → Queue → Workers → PostgreSQL
- ✅ Small-scale testing (17-vote tests for rapid debugging)
- ✅ Fixed results page (localhost:3000/results)
- ✅ Result hiding until after vote submission
- ✅ 30,000 vote load test successful (3,558 votes/sec)
- ✅ Multi-candidate elections working
- ✅ Party colors and branding
- ✅ Real-time auto-refresh (5-second intervals)

## Load Testing

### Generate Test Data

Generate 8 million test vote credentials:
```bash
python3 scripts/preload_test_hashes.py 8000000
```

This creates:
- `test_votes.txt` (251MB, 8M lines)
- Loads all hashes into Redis for validation

### Run Load Tests

**Standard Load Test** (with valid credentials):
```bash
python3 -u tests/load_test.py --votes 100000 --rate 1000
```

**Direct DB Test** (elections, 30k votes):
```bash
python3 tests/test_election_simple.py
```

**Performance Results:**
- **Direct DB**: 3,558 votes/sec
- **API Load Test**: 160-265 votes/sec (with full validation pipeline)
- **System Capacity**: Designed for 8M votes in 24 hours (~92 votes/sec average)

## Scaling for 8M Votes

**Development** (docker-compose):
- Current performance: ~250 votes/second via API
- Direct DB: 3,500+ votes/second
- Good for testing and demos

**Production** (Kubernetes):
- 10x Ingestion API replicas
- 20x Validation Workers
- 3x Aggregation Service
- Redis Cluster (3 nodes)
- PostgreSQL with read replicas
- **Target**: 1000 votes/second sustained

## Testing

```bash
# Run unit tests
pytest tests/unit/

# Run integration tests
pytest tests/integration/

# Load test law voting
python3 -u tests/load_test.py --votes 10000 --rate 100

# Load test elections (direct DB)
python3 tests/test_election_simple.py
```

## Monitoring

Access Grafana at http://localhost:3001 (admin/admin)

**Key Dashboards:**
- **Vote Processing**: Votes/sec, latency, success rate
- **System Health**: Queue depth, Redis memory, DB connections
- **Business Metrics**: Duplicate attempts, votes by law/election

**Real-Time Results:**
- Monitor Dashboard: http://localhost:4000/monitor.html
- Auto-refreshes every 5 seconds
- Color-coded by political party
- Live vote counts and percentages

## Security

- ✅ No PII stored (only hashes)
- ✅ Offline hash database prevents fake votes
- ✅ Duplicate detection via Redis
- ✅ Complete audit trail in PostgreSQL
- ✅ Rate limiting on API
- ✅ Election timing enforcement (no early/late votes)
- ✅ TLS for inter-service communication (production)

## Troubleshooting

**Votes not being processed?**
1. Check RabbitMQ queue depth: `curl -u guest:guest http://localhost:15672/api/queues`
2. Check validation worker logs: `docker-compose logs validation-worker`
3. Verify Redis has hashes: `docker-compose exec redis redis-cli SCARD valid_hashes`

**Election results not showing?**
1. Check election_results table: `docker-compose exec postgres psql -U voting_user -d voting -c "SELECT * FROM election_results;"`
2. Verify candidates exist: Check admin panel Tab 7
3. Check monitor dashboard for live results

**Performance issues?**
1. Check Prometheus metrics: http://localhost:9090
2. Scale validation workers: `docker-compose up -d --scale validation-worker=5`
3. Monitor Redis memory: `docker-compose exec redis redis-cli INFO memory`

## Deployment

### Docker Compose (Local)
```bash
docker-compose up -d
```

### Kubernetes (Production)
```bash
# Apply base configuration
kubectl apply -k k8s/overlays/prod/

# Scale workers
kubectl scale deployment validation-worker --replicas=20

# Check status
kubectl get pods
```

## Recent Updates

### 2025-11-21
- ✅ **Added "All Regions" aggregation** to monitor dashboard
  - National election totals shown by default
  - Automatic vote aggregation across all regions
  - Seamless switching between national and regional views
- ✅ **Created small-scale testing scripts** (17 votes)
  - `tests/small_rabbitmq_test.py` - Test RabbitMQ pipeline
  - `tests/small_election_test.py` - Test election voting
  - Fast debugging without loading 8M votes
- ✅ **Created quick-start.sh** - One-command system startup
- ✅ **Removed redundant law chart** from monitor dashboard
- ✅ Successfully tested complete RabbitMQ pipeline:
  - API → RabbitMQ → Validation Workers → PostgreSQL
  - All 17/17 votes processed correctly
- ✅ Updated README with improved quick-start guide

### 2025-11-16
- ✅ Generated 8 million test vote credentials (251MB file)
- ✅ Loaded 8M hashes into Redis (~2 min load time)
- ✅ Cleaned up 154 Zone.Identifier files
- ✅ Organized test results into `test_results/` folder
- ✅ Updated documentation (README + GEMINI.md)

## Support

For issues and questions, see [ARCHITECTURE.md](./ARCHITECTURE.md) or contact the development team.
