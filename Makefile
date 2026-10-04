# FlaskVerseHub developer entry points. Run `make help` for a summary.
PYTHON   ?= python3
VENV     ?= .venv
BIN      := $(VENV)/bin
PIP      := $(BIN)/pip
PY       := $(BIN)/python
FLASK    := $(BIN)/flask

.DEFAULT_GOAL := help

.PHONY: help venv install install-prod lint format typecheck security test test-fast cov bench \
        experiment run shell db-init db-seed docker-up docker-down clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

venv: ## Create the virtual environment
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip wheel

install: venv ## Install runtime + development dependencies
	$(PIP) install -r requirements/dev.txt
	$(PIP) install -e . --no-deps
	$(BIN)/pre-commit install

install-prod: ## Install runtime + production dependencies
	$(PIP) install -r requirements/prod.txt

lint: ## Run ruff lint and format check
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .

format: ## Auto-format and fix lint issues
	$(BIN)/ruff format .
	$(BIN)/ruff check --fix .

typecheck: ## Run mypy
	$(BIN)/mypy

security: ## Run bandit static security analysis
	$(BIN)/bandit -c pyproject.toml -r app

test: ## Run the full test suite with coverage gate
	$(BIN)/pytest --cov --cov-report=term-missing --cov-report=xml

test-fast: ## Run tests without coverage, stop at first failure
	$(BIN)/pytest -x -q -m "not slow"

cov: test ## Generate HTML coverage report
	$(BIN)/coverage html
	@echo "open htmlcov/index.html"

bench: ## Run micro-benchmarks (pytest-benchmark)
	$(BIN)/pytest tests/research -m slow --benchmark-only --benchmark-sort=mean

experiment: ## Run the reproducible retrieval benchmark
	$(PY) -m experiments.run_retrieval_benchmark --config experiments/configs/default.yaml

run: ## Start the development server
	FLASK_APP=wsgi:app FLASK_CONFIG=development $(FLASK) run --debug

shell: ## Open a Flask shell
	FLASK_APP=wsgi:app $(FLASK) shell

db-init: ## Create database tables and apply migrations
	FLASK_APP=wsgi:app $(FLASK) db upgrade

db-seed: ## Seed the database with demonstration data
	FLASK_APP=wsgi:app $(FLASK) seed all

docker-up: ## Start the full stack with Docker Compose
	docker compose -f docker/docker-compose.yml up --build -d

docker-down: ## Stop the Docker Compose stack
	docker compose -f docker/docker-compose.yml down -v

clean: ## Remove caches and build artefacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov coverage.xml .coverage dist build *.egg-info
	find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} +
