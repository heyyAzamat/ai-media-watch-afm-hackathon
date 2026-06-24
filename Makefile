.PHONY: help install install-ml dev api worker migrate test lint fmt typecheck run-local up down logs clean

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN{FS=":.*?## "}{printf "\033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Install runtime + dev deps (editable)
	pip install -e ".[dev]"

install-ml: ## Install heavy ML providers (GPU nodes)
	pip install -e ".[ml,dev]"

migrate: ## Create database tables
	python -m aimw.scripts.init_db

api: ## Run the API locally (reload)
	uvicorn aimw.main:app --reload --host 0.0.0.0 --port 8000

worker: ## Run a Celery worker locally
	celery -A aimw.workers.celery_app.celery_app worker --loglevel=INFO --concurrency=2

run-local: ## Run the engine on a file with mock providers (no DB/queue)
	python -m aimw.scripts.run_local $(FILE)

test: ## Run the test suite
	pytest

lint: ## Lint with ruff
	ruff check src tests

fmt: ## Auto-format with ruff
	ruff check --fix src tests && ruff format src tests

typecheck: ## Static type check
	mypy src

up: ## Start full stack (Docker)
	docker compose up --build -d

down: ## Stop the stack
	docker compose down

logs: ## Tail stack logs
	docker compose logs -f api worker

clean: ## Remove caches + build artifacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
