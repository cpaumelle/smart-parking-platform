# Dockerfile - Multi-stage build for production

# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY src/ ./src/
COPY migrations/ ./migrations/

# Ensure scripts are in PATH
ENV PATH=/root/.local/bin:$PATH

# Create non-root user (production)
# RUN useradd -m -u 1000 parking && chown -R parking:parking /app
# USER parking

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run application (multi-tenancy enabled)
CMD ["python", "-m", "uvicorn", "src.main_tenanted:app", "--host", "0.0.0.0", "--port", "8000"]
