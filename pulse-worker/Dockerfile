FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

RUN useradd --create-home --shell /usr/sbin/nologin app
USER app

CMD ["python", "-m", "pulse_worker.main"]
