FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install cryptography explicitly (required for Ed25519)
RUN pip install --no-cache-dir cryptography>=41.0.0

# Copy application code
COPY . .

# Expose port for dashboard
EXPOSE 8080

# Railway will use startCommand from railway.json
# If startCommand is not set, Railway will use this CMD
# Railway sets PORT env var automatically
ENV PORT=8080
CMD uvicorn dashboard:app --host 0.0.0.0 --port ${PORT}
