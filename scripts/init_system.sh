#!/bin/bash
#
# System Initialization Script for Distributed Voting System
#
# This script:
# 1. Waits for all services (Redis, RabbitMQ, PostgreSQL) to be healthy
# 2. Initializes RabbitMQ exchanges and queues
# 3. Loads voter hashes into Redis
# 4. Verifies database schema is initialized
# 5. Performs health checks
#
# Usage:
#   ./init_system.sh [--skip-hashes] [--skip-rabbitmq]
#

set -e  # Exit on error

# Configuration
REDIS_HOST="localhost"
REDIS_PORT="${REDIS_PORT:-6379}"
RABBITMQ_HOST="localhost"
RABBITMQ_PORT="${RABBITMQ_PORT:-5672}"
RABBITMQ_MGMT_PORT="${RABBITMQ_MGMT_PORT:-15672}"
RABBITMQ_USER="${RABBITMQ_USER:-guest}"
RABBITMQ_PASSWORD="${RABBITMQ_PASSWORD:-guest}"
POSTGRES_HOST="localhost"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_DB="${POSTGRES_DB:-voting}"
POSTGRES_USER="${POSTGRES_USER:-voting_user}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-voting_password}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse arguments
SKIP_HASHES=false
SKIP_RABBITMQ=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-hashes)
            SKIP_HASHES=true
            shift
            ;;
        --skip-rabbitmq)
            SKIP_RABBITMQ=true
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

wait_for_service() {
    local host=$1
    local port=$2
    local service_name=$3
    local max_attempts=30
    local attempt=1

    log_info "Waiting for $service_name at $host:$port..."

    while ! nc -z "$host" "$port" 2>/dev/null; do
        if [ $attempt -eq $max_attempts ]; then
            log_error "$service_name is not available after $max_attempts attempts"
            return 1
        fi
        echo -n "."
        sleep 2
        ((attempt++))
    done

    echo ""
    log_info "$service_name is available!"
    return 0
}

wait_for_redis() {
    log_info "Checking Redis..."
    if ! command -v redis-cli &> /dev/null; then
        log_warn "redis-cli not found, using netcat for basic check"
        wait_for_service "$REDIS_HOST" "$REDIS_PORT" "Redis"
    else
        local max_attempts=30
        local attempt=1

        while ! redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping &>/dev/null; do
            if [ $attempt -eq $max_attempts ]; then
                log_error "Redis is not available after $max_attempts attempts"
                return 1
            fi
            echo -n "."
            sleep 2
            ((attempt++))
        done

        echo ""
        log_info "Redis is healthy!"
    fi
    return 0
}

wait_for_postgres() {
    log_info "Checking PostgreSQL..."
    if ! command -v psql &> /dev/null; then
        log_warn "psql not found, using netcat for basic check"
        wait_for_service "$POSTGRES_HOST" "$POSTGRES_PORT" "PostgreSQL"
    else
        local max_attempts=30
        local attempt=1

        export PGPASSWORD="$POSTGRES_PASSWORD"
        while ! psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1;" &>/dev/null; do
            if [ $attempt -eq $max_attempts ]; then
                log_error "PostgreSQL is not available after $max_attempts attempts"
                return 1
            fi
            echo -n "."
            sleep 2
            ((attempt++))
        done

        echo ""
        log_info "PostgreSQL is healthy!"
    fi
    return 0
}

wait_for_rabbitmq() {
    log_info "Checking RabbitMQ..."
    wait_for_service "$RABBITMQ_HOST" "$RABBITMQ_PORT" "RabbitMQ (AMQP)"
    wait_for_service "$RABBITMQ_HOST" "$RABBITMQ_MGMT_PORT" "RabbitMQ (Management)"

    # Additional health check via management API
    local max_attempts=30
    local attempt=1

    while ! curl -s -u "$RABBITMQ_USER:$RABBITMQ_PASSWORD" \
        "http://$RABBITMQ_HOST:$RABBITMQ_MGMT_PORT/api/healthchecks/node" &>/dev/null; do
        if [ $attempt -eq $max_attempts ]; then
            log_warn "RabbitMQ management API not responding, continuing anyway..."
            break
        fi
        echo -n "."
        sleep 2
        ((attempt++))
    done

    echo ""
    log_info "RabbitMQ is healthy!"
    return 0
}

init_rabbitmq() {
    if [ "$SKIP_RABBITMQ" = true ]; then
        log_warn "Skipping RabbitMQ initialization"
        return 0
    fi

    log_info "Initializing RabbitMQ exchanges and queues..."

    # Create exchange
    log_info "Creating exchange 'votes'..."
    curl -s -u "$RABBITMQ_USER:$RABBITMQ_PASSWORD" \
        -X PUT \
        -H "content-type:application/json" \
        "http://$RABBITMQ_HOST:$RABBITMQ_MGMT_PORT/api/exchanges/%2F/votes" \
        -d '{"type":"topic","durable":true}' || log_warn "Exchange may already exist"

    # Create bindings
    log_info "Creating queue bindings..."
    curl -s -u "$RABBITMQ_USER:$RABBITMQ_PASSWORD" \
        -X POST \
        -H "content-type:application/json" \
        "http://$RABBITMQ_HOST:$RABBITMQ_MGMT_PORT/api/bindings/%2F/e/votes/q/validation_queue" \
        -d '{"routing_key":"vote.validation"}' || log_warn "Binding may already exist"

    curl -s -u "$RABBITMQ_USER:$RABBITMQ_PASSWORD" \
        -X POST \
        -H "content-type:application/json" \
        "http://$RABBITMQ_HOST:$RABBITMQ_MGMT_PORT/api/bindings/%2F/e/votes/q/aggregation_queue" \
        -d '{"routing_key":"vote.aggregation"}' || log_warn "Binding may already exist"

    curl -s -u "$RABBITMQ_USER:$RABBITMQ_PASSWORD" \
        -X POST \
        -H "content-type:application/json" \
        "http://$RABBITMQ_HOST:$RABBITMQ_MGMT_PORT/api/bindings/%2F/e/votes/q/review_queue" \
        -d '{"routing_key":"vote.review"}' || log_warn "Binding may already exist"

    log_info "RabbitMQ initialization complete!"
}

load_hashes() {
    if [ "$SKIP_HASHES" = true ]; then
        log_warn "Skipping hash loading"
        return 0
    fi

    log_info "Loading voter hashes into Redis..."

    # Find the script directory
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    HASH_LOADER="$SCRIPT_DIR/load_hashes_to_redis.py"

    if [ ! -f "$HASH_LOADER" ]; then
        log_error "Hash loader script not found: $HASH_LOADER"
        return 1
    fi

    # Check if Python is available
    if ! command -v python3 &> /dev/null; then
        log_error "python3 is required but not installed"
        return 1
    fi

    # Run the hash loader
    python3 "$HASH_LOADER" \
        --redis-host "$REDIS_HOST" \
        --redis-port "$REDIS_PORT" \
        --redis-db 0 \
        --batch-size 10000

    if [ $? -eq 0 ]; then
        log_info "Hash loading complete!"
    else
        log_error "Hash loading failed!"
        return 1
    fi
}

verify_database() {
    log_info "Verifying database schema..."

    if ! command -v psql &> /dev/null; then
        log_warn "psql not found, skipping database verification"
        return 0
    fi

    export PGPASSWORD="$POSTGRES_PASSWORD"

    # Check if tables exist
    local tables=$(psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
        -t -c "SELECT table_name FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null | grep -v '^$' | wc -l)

    if [ "$tables" -gt 0 ]; then
        log_info "Database schema initialized with $tables table(s)"
    else
        log_warn "No tables found in database - schema may not be initialized"
    fi
}

system_health_check() {
    log_info "Performing system health check..."

    # Check Redis
    if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping &>/dev/null; then
        local hash_count=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" SCARD valid_hashes 2>/dev/null || echo "0")
        log_info "✓ Redis is healthy (valid_hashes: $hash_count)"
    else
        log_warn "✗ Redis health check failed"
    fi

    # Check RabbitMQ
    if curl -s -u "$RABBITMQ_USER:$RABBITMQ_PASSWORD" \
        "http://$RABBITMQ_HOST:$RABBITMQ_MGMT_PORT/api/overview" &>/dev/null; then
        log_info "✓ RabbitMQ is healthy"
    else
        log_warn "✗ RabbitMQ health check failed"
    fi

    # Check PostgreSQL
    if psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1;" &>/dev/null; then
        log_info "✓ PostgreSQL is healthy"
    else
        log_warn "✗ PostgreSQL health check failed"
    fi
}

# Main execution
main() {
    log_info "Starting system initialization..."
    echo ""

    # Wait for all services
    wait_for_redis || exit 1
    wait_for_rabbitmq || exit 1
    wait_for_postgres || exit 1

    echo ""
    log_info "All services are ready!"
    echo ""

    # Initialize RabbitMQ
    init_rabbitmq || log_warn "RabbitMQ initialization had issues"

    echo ""

    # Load hashes
    load_hashes || log_warn "Hash loading had issues"

    echo ""

    # Verify database
    verify_database

    echo ""

    # Final health check
    system_health_check

    echo ""
    log_info "System initialization complete!"
}

# Run main function
main
