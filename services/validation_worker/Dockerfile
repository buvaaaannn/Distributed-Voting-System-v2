# Multi-stage build for validation worker
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt


# Final stage
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user first
RUN useradd -m -u 1000 worker

# Copy Python dependencies from builder to the new user's home directory
COPY --from=builder --chown=worker:worker /root/.local /home/worker/.local

# Add the new user's local bin to the PATH
ENV PATH=/home/worker/.local/bin:$PATH

# Copy application code
COPY --chown=worker:worker . .

# Switch to non-root user
USER worker

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Expose Prometheus metrics port
EXPOSE 8001

# Set Python to run in unbuffered mode
ENV PYTHONUNBUFFERED=1

# Run the worker
CMD ["python", "worker.py"]
