# Pulse API

FastAPI backend for the Pulse multilingual content generation platform.

## Quick Start

```bash
cd pulse-api
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn pulse.main:app --reload --port 8000
```

## Tests

```bash
pytest tests -v
ruff check src tests
mypy src
```

## Migrations

```bash
alembic upgrade head
```
