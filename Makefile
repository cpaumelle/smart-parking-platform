.PHONY: help install dev test lint format clean run migrate backup

help:
	@echo "Smart Parking v2 - Available commands:"
	@echo ""
	@echo "  make install      Install production dependencies"
	@echo "  make dev          Install development dependencies"
	@echo "  make test         Run tests"
	@echo "  make lint         Run linter (ruff)"
	@echo "  make format       Format code (black)"
	@echo "  make clean        Clean cache files"
	@echo "  make run          Run development server"
	@echo "  make migrate      Run database migrations"
	@echo "  make backup       Backup database"
	@echo ""

install:
	pip install -r requirements.txt

dev:
	pip install -r requirements.txt -r requirements-dev.txt

test:
	pytest tests/ -v

lint:
	ruff check src/
	mypy src/

format:
	black src/ tests/
	ruff check --fix src/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true

run:
	uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

migrate:
	psql $(DATABASE_URL) -f migrations/001_initial_schema.sql

backup:
	@echo "Creating backup..."
	@mkdir -p backups
	@pg_dump $(DATABASE_URL) > backups/backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "Backup created in backups/"
