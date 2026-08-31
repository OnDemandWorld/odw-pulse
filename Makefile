.PHONY: help install dev api worker scheduler ui test lint typecheck build

help:
	@echo "Pulse development commands:"
	@echo "  make install    - Create pulse-api/.venv and install all Python packages"
	@echo "  make dev        - Start Docker Compose stack"
	@echo "  make api        - Run API server locally"
	@echo "  make worker     - Run worker locally"
	@echo "  make scheduler  - Run scheduler locally"
	@echo "  make ui         - Run UI dev server"
	@echo "  make test       - Run backend tests"
	@echo "  make lint       - Run ruff on backend"
	@echo "  make typecheck  - Run mypy on backend"
	@echo "  make build      - Build all Docker images"

# One shared venv for all three Python packages. pulse-worker and
# pulse-scheduler are separate distributions, so they must be installed
# editable alongside pulse-api for `make worker` / `make scheduler` to work.
install:
	cd pulse-api && python3 -m venv .venv && \
		.venv/bin/pip install -U pip && \
		.venv/bin/pip install -e ".[dev]" -e ../pulse-worker -e ../pulse-scheduler

dev:
	docker compose up --build

api:
	cd pulse-api && source .venv/bin/activate && uvicorn pulse.main:app --reload --port 8000

worker:
	cd pulse-api && source .venv/bin/activate && python -m pulse_worker.main

scheduler:
	cd pulse-api && source .venv/bin/activate && python -m pulse_scheduler.main

ui:
	cd pulse-ui && npm run dev

test:
	cd pulse-api && source .venv/bin/activate && pytest tests -v

lint:
	cd pulse-api && source .venv/bin/activate && ruff check src tests

typecheck:
	cd pulse-api && source .venv/bin/activate && mypy src

build:
	docker build -t ondemandworld/pulse-api:latest pulse-api
	docker build -t ondemandworld/pulse-worker:latest pulse-worker
	docker build -t ondemandworld/pulse-scheduler:latest pulse-scheduler
	docker build -t ondemandworld/pulse-ui:latest pulse-ui
