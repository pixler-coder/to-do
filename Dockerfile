# ── NeoTask Production Dockerfile ──────────────────────────────────
FROM python:3.12-slim AS base

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ backend/
COPY frontend/ frontend/

# Create a non-root user for security
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup appuser && \
    # Create writable directory for SQLite database
    mkdir -p /app/data && \
    chown -R appuser:appgroup /app/data

USER appuser

# Default environment variables (override at runtime)
ENV DATABASE_URL=sqlite:///./data/todo.db \
    ALLOWED_ORIGINS=http://127.0.0.1:8000,http://localhost:8000 \
    DEBUG=false \
    LOG_LEVEL=INFO

EXPOSE 8000

# Health check for container orchestrators (Docker, ECS, K8s)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

# Run with Gunicorn using Uvicorn workers for production-grade serving
CMD ["gunicorn", "backend.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "4", \
     "--bind", "0.0.0.0:8000", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
