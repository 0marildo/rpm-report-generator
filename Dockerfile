# Production container for the combined FastAPI and Gradio application.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PORT=8080

WORKDIR /app

# Install dependencies separately so Docker can reuse this layer when only
# application code changes.
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml run_api.py ./
COPY src ./src
COPY templates ./templates
COPY static ./static

# Cloud Run runs the image as an unprivileged user. The application writes
# temporary uploads and reports under /tmp, which remains writable.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

CMD ["python", "run_api.py"]
