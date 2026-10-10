# Multi-stage lightweight container build for Google Cloud Run
FROM python:3.11-slim as base

# Set environment flags
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8080

# Install minimal OS security updates and curl for container health check
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root application user for least-privilege container execution
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/false -m appuser

WORKDIR /app

# Install Python production dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY src/ /app/src/

# Change file ownership to non-root user
RUN chown -R appuser:appgroup /app

# Switch to non-root user
USER 10001:10001

# Expose standard Cloud Run HTTP port
EXPOSE 8080

# Run Uvicorn ASGI server
CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8080"]
