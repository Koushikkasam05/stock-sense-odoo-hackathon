# Multi-stage Dockerfile for StockSense Inventory Management System
FROM python:3.12-slim as builder

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system build dependencies for psycopg2 and cryptography
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Final runtime image
FROM python:3.12-slim

WORKDIR /app

# Install runtime PostgreSQL client library
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed wheels from builder
COPY --from=builder /install /usr/local

# Copy application source code
COPY . .

# Set permissions
RUN useradd -m -u 1000 stocksense && chown -R stocksense:stocksense /app
USER stocksense

# Expose default port
EXPOSE 5000

# Health check against Flask health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Production WSGI startup command
CMD ["gunicorn", "-c", "gunicorn.conf.py", "wsgi:app"]
