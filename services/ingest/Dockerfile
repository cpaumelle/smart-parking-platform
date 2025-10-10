# Dockerfile - Version: 1.1.0 - 2025-08-02 17:30 UTC
# Changelog:
# - Installed cron
# - Installed nano (optional for debugging)
# - Added cronjobs.txt from tools/
# - Started both cron and uvicorn via shell CMD

FROM python:3.11-slim

# Install system packages (cron and optional nano for debugging)
RUN apt-get update && apt-get install -y cron nano && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy source code
COPY ./app /app
COPY ./tools /app/tools
COPY requirements.txt .
COPY ./tools/cronjobs.txt /app/cronjobs.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Register cron job
RUN crontab /app/cronjobs.txt

# Start both cron and uvicorn via bash
CMD bash -c "service cron start && uvicorn main:app --host 0.0.0.0 --port 8000"
