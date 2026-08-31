FROM python:3.11-slim

WORKDIR /app

# Build context is the repository root (see docker-compose.yml and the
# Makefile). pulse-worker consumes pulse-api's bulk-job pipeline, so both
# packages are installed into the image.
COPY pulse-api/pyproject.toml pulse-api/README.md ./pulse-api/
COPY pulse-api/src ./pulse-api/src
COPY pulse-worker/pyproject.toml pulse-worker/README.md ./pulse-worker/
COPY pulse-worker/src ./pulse-worker/src

RUN pip install --no-cache-dir ./pulse-api ./pulse-worker

RUN useradd --create-home --shell /usr/sbin/nologin app
USER app

CMD ["python", "-m", "pulse_worker.main"]
