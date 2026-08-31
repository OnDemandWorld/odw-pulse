FROM python:3.11-slim

WORKDIR /app

# Build context is the repository root (see docker-compose.yml and the
# Makefile). pulse-scheduler's bulk-job reaper uses pulse-api's maintenance
# helpers, so both packages are installed into the image.
COPY pulse-api/pyproject.toml pulse-api/README.md ./pulse-api/
COPY pulse-api/src ./pulse-api/src
COPY pulse-scheduler/pyproject.toml pulse-scheduler/README.md ./pulse-scheduler/
COPY pulse-scheduler/src ./pulse-scheduler/src

RUN pip install --no-cache-dir ./pulse-api ./pulse-scheduler

RUN useradd --create-home --shell /usr/sbin/nologin app
USER app

CMD ["python", "-m", "pulse_scheduler.main"]
