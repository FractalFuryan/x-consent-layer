# X Identity Shield — Consent Layer
# Production Dockerfile (CPU-only, minimal dependencies)

FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY consent_core.py .
COPY consent_api.py .

# Create directories for persistent data
RUN mkdir -p /data

# Non-root user for security
RUN useradd -m -u 1000 consent && chown -R consent:consent /app /data
USER consent

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/docs')" || exit 1

# Run API server
CMD ["uvicorn", "consent_api:app", "--host", "0.0.0.0", "--port", "8000"]
