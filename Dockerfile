# syntax=docker/dockerfile:1

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system deps (minimal). Most scientific wheels are prebuilt.
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first for better layer caching
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . /app

EXPOSE 8001

# Default storage dir inside container (can be overridden via env)
ENV STORAGE_ROOT=/app/public/uploads

# Ensure storage dir exists at runtime
RUN mkdir -p /data/rrd

# Start server
CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8001"]
