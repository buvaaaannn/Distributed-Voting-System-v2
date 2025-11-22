# Makefile for Distributed Voting System
# Provides convenient commands for Docker Compose operations

.PHONY: help build up down restart logs clean init test scale-workers

# Default target
.DEFAULT_GOAL := help

# Color output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

help: ## Show this help message
	@echo "$(BLUE)Distributed Voting System - Docker Commands$(NC)"
	@echo ""
	@echo "$(GREEN)Available targets:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""

build: ## Build all Docker images
	@echo "$(BLUE)Building all services...$(NC)"
	docker-compose build

up: ## Start all services
	@echo "$(GREEN)Starting all services...$(NC)"
	docker-compose up -d
	@echo "$(GREEN)Waiting for services to be healthy...$(NC)"
	@sleep 10
	@echo "$(GREEN)Services started! Use 'make logs' to view logs$(NC)"

up-dev: ## Start all services with development configuration
	@echo "$(GREEN)Starting services in development mode...$(NC)"
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
	@sleep 10
	@echo "$(GREEN)Development environment started!$(NC)"

down: ## Stop all services
	@echo "$(YELLOW)Stopping all services...$(NC)"
	docker-compose down

down-clean: ## Stop all services and remove volumes (WARNING: deletes all data)
	@echo "$(RED)WARNING: This will delete ALL data including volumes!$(NC)"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker-compose down -v; \
		echo "$(RED)All services and data removed$(NC)"; \
	fi

restart: ## Restart all services
	@echo "$(YELLOW)Restarting all services...$(NC)"
	docker-compose restart

restart-api: ## Restart ingestion API only
	@echo "$(YELLOW)Restarting ingestion API...$(NC)"
	docker-compose restart ingestion-api

restart-workers: ## Restart validation workers only
	@echo "$(YELLOW)Restarting validation workers...$(NC)"
	docker-compose restart validation-worker

logs: ## View logs from all services
	docker-compose logs -f

logs-api: ## View logs from ingestion API
	docker-compose logs -f ingestion-api

logs-worker: ## View logs from validation workers
	docker-compose logs -f validation-worker

logs-aggregation: ## View logs from aggregation service
	docker-compose logs -f aggregation

ps: ## Show running containers
	docker-compose ps

init: ## Initialize the system (run after first 'make up')
	@echo "$(BLUE)Initializing system...$(NC)"
	@chmod +x scripts/init_system.sh
	@chmod +x scripts/load_hashes_to_redis.py
	./scripts/init_system.sh
	@echo "$(GREEN)System initialized!$(NC)"

init-skip-hashes: ## Initialize system without loading hashes
	@echo "$(BLUE)Initializing system (skipping hash load)...$(NC)"
	./scripts/init_system.sh --skip-hashes

load-hashes: ## Load voter hashes into Redis
	@echo "$(BLUE)Loading voter hashes...$(NC)"
	python3 scripts/load_hashes_to_redis.py \
		--redis-host localhost \
		--redis-port 6379 \
		--batch-size 10000

scale-workers: ## Scale validation workers (usage: make scale-workers WORKERS=5)
	@if [ -z "$(WORKERS)" ]; then \
		echo "$(RED)Error: WORKERS parameter required$(NC)"; \
		echo "Usage: make scale-workers WORKERS=5"; \
		exit 1; \
	fi
	@echo "$(BLUE)Scaling validation workers to $(WORKERS)...$(NC)"
	docker-compose up -d --scale validation-worker=$(WORKERS)

health: ## Check health of all services
	@echo "$(BLUE)Checking service health...$(NC)"
	@echo ""
	@echo "$(YELLOW)Redis:$(NC)"
	@docker-compose exec redis redis-cli ping || echo "$(RED)Redis is not responding$(NC)"
	@echo ""
	@echo "$(YELLOW)RabbitMQ:$(NC)"
	@curl -s -u guest:guest http://localhost:15672/api/overview > /dev/null && echo "$(GREEN)RabbitMQ is healthy$(NC)" || echo "$(RED)RabbitMQ is not responding$(NC)"
	@echo ""
	@echo "$(YELLOW)PostgreSQL:$(NC)"
	@docker-compose exec postgres psql -U voting_user -d voting -c "SELECT 1" > /dev/null 2>&1 && echo "$(GREEN)PostgreSQL is healthy$(NC)" || echo "$(RED)PostgreSQL is not responding$(NC)"
	@echo ""
	@echo "$(YELLOW)Ingestion API:$(NC)"
	@curl -s http://localhost:8000/health > /dev/null && echo "$(GREEN)API is healthy$(NC)" || echo "$(RED)API is not responding$(NC)"

stats: ## Show system statistics
	@echo "$(BLUE)System Statistics$(NC)"
	@echo ""
	@echo "$(YELLOW)Redis:$(NC)"
	@echo "  Valid hashes: $$(docker-compose exec redis redis-cli SCARD valid_hashes 2>/dev/null || echo 'N/A')"
	@echo "  Voted hashes: $$(docker-compose exec redis redis-cli SCARD voted_hashes 2>/dev/null || echo 'N/A')"
	@echo ""
	@echo "$(YELLOW)RabbitMQ Queues:$(NC)"
	@curl -s -u guest:guest http://localhost:15672/api/queues 2>/dev/null | python3 -m json.tool | grep -E '(name|messages)' || echo "  Unable to fetch queue stats"
	@echo ""
	@echo "$(YELLOW)Database:$(NC)"
	@docker-compose exec postgres psql -U voting_user -d voting -t -c "SELECT COUNT(*) FROM vote_audit" 2>/dev/null | xargs echo "  Total votes in audit:" || echo "  Unable to fetch database stats"

shell-redis: ## Open Redis CLI
	docker-compose exec redis redis-cli

shell-postgres: ## Open PostgreSQL CLI
	docker-compose exec postgres psql -U voting_user -d voting

shell-api: ## Open shell in ingestion API container
	docker-compose exec ingestion-api /bin/sh

clean-logs: ## Clean up Docker logs
	@echo "$(YELLOW)Cleaning up Docker logs...$(NC)"
	docker-compose logs --tail=0 2>&1 > /dev/null

rebuild: down build up ## Rebuild and restart all services

rebuild-api: ## Rebuild and restart ingestion API
	@echo "$(BLUE)Rebuilding ingestion API...$(NC)"
	docker-compose build ingestion-api
	docker-compose up -d ingestion-api

rebuild-worker: ## Rebuild and restart validation workers
	@echo "$(BLUE)Rebuilding validation workers...$(NC)"
	docker-compose build validation-worker
	docker-compose up -d validation-worker

# Development targets
dev: up-dev init ## Start development environment and initialize

# URLs
urls: ## Show service URLs
	@echo "$(BLUE)Service URLs:$(NC)"
	@echo ""
	@echo "$(GREEN)Ingestion API:$(NC)          http://localhost:8000"
	@echo "$(GREEN)API Documentation:$(NC)      http://localhost:8000/docs"
	@echo "$(GREEN)RabbitMQ Management:$(NC)    http://localhost:15672 (guest/guest)"
	@echo "$(GREEN)Grafana:$(NC)                http://localhost:3001 (admin/admin)"
	@echo "$(GREEN)Prometheus:$(NC)             http://localhost:9090"
	@echo "$(GREEN)Adminer (dev):$(NC)          http://localhost:8080"
	@echo ""

# Backup and restore
backup-db: ## Backup PostgreSQL database
	@echo "$(BLUE)Backing up database...$(NC)"
	@mkdir -p backups
	docker-compose exec -T postgres pg_dump -U voting_user voting > backups/voting_backup_$$(date +%Y%m%d_%H%M%S).sql
	@echo "$(GREEN)Database backed up to backups/$(NC)"

restore-db: ## Restore PostgreSQL database (usage: make restore-db FILE=backups/voting_backup.sql)
	@if [ -z "$(FILE)" ]; then \
		echo "$(RED)Error: FILE parameter required$(NC)"; \
		echo "Usage: make restore-db FILE=backups/voting_backup.sql"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Restoring database from $(FILE)...$(NC)"
	docker-compose exec -T postgres psql -U voting_user voting < $(FILE)
	@echo "$(GREEN)Database restored!$(NC)"

# Testing
test: ## Run tests in containers
	@echo "$(BLUE)Running tests...$(NC)"
	docker-compose exec ingestion-api pytest
	docker-compose exec validation-worker pytest

# Monitoring
monitor: ## Open monitoring tools in browser
	@echo "$(BLUE)Opening monitoring tools...$(NC)"
	@command -v xdg-open > /dev/null && xdg-open http://localhost:3001 || open http://localhost:3001 || echo "$(YELLOW)Please open http://localhost:3001 manually$(NC)"
	@command -v xdg-open > /dev/null && xdg-open http://localhost:15672 || open http://localhost:15672 || echo "$(YELLOW)Please open http://localhost:15672 manually$(NC)"
