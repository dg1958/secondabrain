# Memory Palace Dockerfile
# Multi-stage build for optimized image size

# =============================================================================
# Stage 1: Build stage
# =============================================================================
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better cache
COPY requirements.txt .

# Create virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# =============================================================================
# Stage 2: Runtime stage
# =============================================================================
FROM python:3.11-slim as runtime

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p /app/data

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app
ENV MEMORY_PALACE_DATA=/app/data
ENV METRICS_ENABLED=true

# Expose ports
# 8000 - REST API with metrics endpoint
# 8765 - MCP HTTP/SSE transport
EXPOSE 8000 8765

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command - run REST API server with metrics
CMD ["python", "-m", "uvicorn", "api.rest_api:app", "--host", "0.0.0.0", "--port", "8000"]
