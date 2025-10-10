# Dockerfile - Downlink Service
# Version: 1.0.0 - 2025-10-07
# Purpose: ChirpStack gRPC API wrapper for downlink management

FROM python:3.11-slim

# Install system packages
RUN apt-get update && apt-get install -y nano && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy application files
COPY ./app /app

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port
EXPOSE 8000

# Start uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
