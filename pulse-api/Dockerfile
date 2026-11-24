FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (without src/) to leverage layer caching.
# Only the build-system backend is needed to resolve the hatchling build.
# Dependency layer caching (audit finding #71): install deps against a
# stub package first so source edits don't reinstall the world.
COPY pyproject.toml README.md alembic.ini ./
RUN mkdir -p src/pulse && touch src/pulse/__init__.py \
    && pip install --no-cache-dir . \
    && rm -rf src
COPY src ./src
RUN pip install --no-cache-dir --no-deps .

RUN useradd --create-home --shell /usr/sbin/nologin app
USER app

EXPOSE 8000

# Honor PULSE_API_HOST / PULSE_API_PORT (audit finding #74).
CMD ["sh", "-c", "uvicorn pulse.main:app --host ${PULSE_API_HOST:-0.0.0.0} --port ${PULSE_API_PORT:-8000}"]
