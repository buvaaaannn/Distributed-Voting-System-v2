.PHONY: help install run test docker-build docker-run docker-compose-up docker-compose-down clean init-db publish-test-votes

help:
	@echo "Vote Aggregation Service - Makefile Commands"
	@echo "=============================================="
	@echo "install              - Install Python dependencies"
	@echo "run                  - Run the aggregator locally"
	@echo "test                 - Run tests"
	@echo "docker-build         - Build Docker image"
	@echo "docker-run           - Run Docker container"
	@echo "docker-compose-up    - Start all services with docker-compose"
	@echo "docker-compose-down  - Stop all services"
	@echo "init-db              - Initialize database schema"
	@echo "publish-test-votes   - Publish test votes to RabbitMQ"
	@echo "clean                - Clean up generated files"

install:
	pip install -r requirements.txt

run:
	python aggregator.py

test:
	pytest tests/ -v

docker-build:
	docker build -t vote-aggregator:latest .

docker-run: docker-build
	docker run -d \
		--name vote-aggregator \
		-p 8001:8001 \
		-e RABBITMQ_HOST=host.docker.internal \
		-e POSTGRES_HOST=host.docker.internal \
		vote-aggregator:latest

docker-compose-up:
	docker-compose up -d

docker-compose-down:
	docker-compose down

docker-compose-logs:
	docker-compose logs -f aggregator

init-db:
	psql -U postgres -d election_votes -f init_db.sql

publish-test-votes:
	python test_publisher.py -n 1000

publish-many-votes:
	python test_publisher.py -n 10000

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.log" -delete

format:
	black *.py
	isort *.py

lint:
	flake8 *.py
	pylint *.py

metrics:
	curl http://localhost:8001/metrics

check-queue:
	docker exec election-rabbitmq rabbitmqctl list_queues

check-db:
	docker exec election-postgres psql -U postgres -d election_votes -c "SELECT * FROM vote_statistics;"
