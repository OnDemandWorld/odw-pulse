FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (without src/) to leverage layer caching.
# Only the build-system backend is needed to resolve the hatchling build.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

RUN useradd --create-home --shell /usr/sbin/nologin app
USER app

EXPOSE 8000

CMD ["uvicorn", "pulse.main:app", "--host", "0.0.0.0", "--port", "8000"]
