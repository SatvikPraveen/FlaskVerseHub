# File: docker/Dockerfile

FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    PORT=8000

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
        && rm -rf /var/lib/apt/lists/*

# Create app directory and user
RUN groupadd -r flaskuser && useradd -r -g flaskuser flaskuser
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements/ requirements/
RUN pip install --no-cache-dir -r requirements/prod.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p uploads logs \
    && chown -R flaskuser:flaskuser /app

# Switch to non-root user
USER flaskuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--worker-class", "eventlet", "--worker-connections", "1000", "--timeout", "120", "--keep-alive", "2", "--log-level", "info", "wsgi:app"]