.PHONY: help install dev run test lint format clean docker-build docker-up docker-down docker-dev docker-logs

# Default target
help:
	@echo "Nigerian LLC Tax Tracker - Available Commands"
	@echo ""
	@echo "Local Development:"
	@echo "  make install     Install dependencies"
	@echo "  make dev         Run development server with hot reload"
	@echo "  make run         Run production server"
	@echo "  make test        Run tests"
	@echo "  make lint        Run linter"
	@echo "  make format      Format code"
	@echo "  make clean       Clean up cache files"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build   Build Docker image"
	@echo "  make docker-up      Start containers"
	@echo "  make docker-down    Stop containers"
	@echo "  make docker-dev     Start dev container with hot reload"
	@echo "  make docker-logs    View container logs"
	@echo "  make docker-shell   Open shell in container"

# Local development
install:
	poetry install

dev:
	poetry run uvicorn main:app --reload --host 0.0.0.0 --port 8000

run:
	poetry run uvicorn main:app --host 0.0.0.0 --port 8000

test:
	poetry run pytest -v

lint:
	poetry run ruff check .

format:
	poetry run ruff format .
	poetry run ruff check --fix .

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true

# Docker commands
docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-dev:
	docker compose --profile dev up dev

docker-logs:
	docker compose logs -f

docker-shell:
	docker compose exec app /bin/bash

# Create data directory if it doesn't exist
init:
	mkdir -p data
	@echo "Data directory created"
