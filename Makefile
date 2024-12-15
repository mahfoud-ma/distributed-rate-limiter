# Makefile for Distributed Rate Limiter

.PHONY: help install test run docker-up docker-down docker-logs clean format lint

help:  ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install Python dependencies
	pip install -r requirements.txt

test:  ## Run unit tests
	pytest tests/ -v

test-coverage:  ## Run tests with coverage report
	pytest tests/ --cov=app --cov-report=html --cov-report=term

run:  ## Run the application locally
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

docker-build:  ## Build Docker image
	docker-compose build

docker-up:  ## Start services with Docker Compose
	docker-compose up -d
	@echo "Services started! API available at http://localhost:8000"
	@echo "Documentation at http://localhost:8000/docs"

docker-down:  ## Stop Docker Compose services
	docker-compose down

docker-logs:  ## Show Docker Compose logs
	docker-compose logs -f

docker-ha-up:  ## Start HA setup with Sentinel
	docker-compose -f docker-compose.sentinel.yml up -d
	@echo "HA setup started! API available at http://localhost:8000"

docker-ha-down:  ## Stop HA setup
	docker-compose -f docker-compose.sentinel.yml down

docker-ps:  ## Show running containers
	docker-compose ps

load-test:  ## Run load test
	python scripts/load_test.py --requests 1000 --concurrent 50

failover-test:  ## Test Redis Sentinel failover
	./scripts/test_failover.sh

redis-cli:  ## Connect to Redis CLI
	docker exec -it rate_limiter_redis redis-cli

format:  ## Format code with black
	@if command -v black > /dev/null; then \
		black app/ tests/; \
	else \
		echo "black not installed. Run: pip install black"; \
	fi

lint:  ## Lint code with flake8
	@if command -v flake8 > /dev/null; then \
		flake8 app/ tests/ --max-line-length=100; \
	else \
		echo "flake8 not installed. Run: pip install flake8"; \
	fi

clean:  ## Clean up temporary files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	@echo "Cleaned up temporary files"

dev-setup:  ## Complete development setup
	@echo "Setting up development environment..."
	python -m venv venv
	@echo "Virtual environment created!"
	@echo "Activate it with: source venv/bin/activate"
	@echo "Then run: make install"

check:  ## Run all checks (tests + lint)
	@echo "Running tests..."
	@make test
	@echo "\nRunning linter..."
	@make lint
	@echo "\nAll checks passed!"
