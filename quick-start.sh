#!/usr/bin/env bash
##
## QUICK START SCRIPT - Distributed Voting System
## Author: David Marleau
## Project: Demo Version - Functional but incomplete
## Starts all necessary services with a single command
##

set -e  # Exit on error

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  🗳️  Distributed Voting System - Quick Start               ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running"
    echo "   Please start Docker and try again"
    exit 1
fi

echo "📦 Step 1/5: Starting Docker services..."
docker-compose up -d
echo "✅ Docker services started"
echo ""

echo "⏳ Step 2/5: Waiting for services to start (15s)..."
sleep 15
echo "✅ Services ready"
echo ""

echo "🔧 Step 3/5: Starting monitor dashboard..."
python3 monitor_dashboard/server.py > /tmp/monitor_dashboard.log 2>&1 &
MONITOR_PID=$!
echo "✅ Monitor dashboard started (PID: $MONITOR_PID)"
echo ""

echo "🌐 Step 4/5: Starting voting interface (demo UI)..."
cd demo_ui
python3 app.py > /tmp/demo_ui.log 2>&1 &
DEMO_PID=$!
cd ..
echo "✅ Voting interface started (PID: $DEMO_PID)"
echo ""

echo "⏳ Step 5/5: Waiting for web interfaces to start (5s)..."
sleep 5
echo ""

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  ✅ SYSTEM STARTED SUCCESSFULLY!                            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "🌐 AVAILABLE WEB INTERFACES:"
echo ""
echo "   📊 Monitor Dashboard (Live Results)"
echo "      http://localhost:4000/monitor.html"
echo "      - Law voting results"
echo "      - Election results by region"
echo "      - Automatic national aggregation"
echo "      - Auto-refresh every 5 seconds"
echo ""
echo "   🗳️  Voting Interface"
echo "      http://localhost:3000"
echo "      - Vote on laws (Yes/No)"
echo "      - Vote for elections"
echo "      - View results"
echo ""
echo "   ⚙️  Admin Panel (Streamlit)"
echo "      http://localhost:8501"
echo "      - Create elections"
echo "      - Add candidates"
echo "      - Configure voting (single/ranked choice)"
echo ""
echo "   📡 Voting API"
echo "      http://localhost:8000/docs"
echo "      - Interactive Swagger documentation"
echo ""
echo "   🐰 RabbitMQ Management"
echo "      http://localhost:15672"
echo "      - Username: guest / Password: guest"
echo ""
echo "   📈 Grafana (Monitoring)"
echo "      http://localhost:3001"
echo "      - Username: admin / Password: admin"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💡 QUICK TESTS:"
echo ""
echo "   Test with 17 votes (fast):"
echo "   $ python3 tests/small_rabbitmq_test.py"
echo "   $ python3 tests/small_election_test.py"
echo ""
echo "   Generate 8M test votes:"
echo "   $ python3 scripts/preload_test_hashes.py 8000000"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🛑 TO STOP THE SYSTEM:"
echo "   $ docker-compose down"
echo "   $ kill $MONITOR_PID $DEMO_PID"
echo ""
echo "📚 DOCUMENTATION:"
echo "   README.md - Complete guide"
echo "   ARCHITECTURE.md - System architecture"
echo ""
echo "═══════════════════════════════════════════════════════════════"
