# 2b-transform-server/Dockerfile
# Version: 0.2.4 - 2025-07-22 20:05 UTC
# Changelog:
# - FIXED: cronjobs now use full python path and ENV correctly
# - ADD: chmod on async scripts + clean cron setup

FROM python:3.11-slim

# ─── Env Setup ─────────────────────────────────────────────
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# ─── Copy App and Requirements ─────────────────────────────
COPY ./app/ /app/
COPY requirements.txt /app/
COPY ./app/entrypoint.sh /app/entrypoint.sh
COPY ./app/cronjobs.txt /app/cronjobs.txt

# ─── System Dependencies ───────────────────────────────────
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    cron \
    curl \
    nano \
    && rm -rf /var/lib/apt/lists/*

# ─── Python Dependencies ───────────────────────────────────
RUN pip install --no-cache-dir -r requirements.txt

# ─── Make Scripts Executable ───────────────────────────────
RUN chmod +x /app/entrypoint.sh && chmod +x /app/async_tasks/*.py

# ─── Setup Cron ────────────────────────────────────────────
RUN touch /var/log/cron.log /var/log/cron_heartbeat.log && \
    chmod 666 /var/log/cron*.log && \
    crontab /app/cronjobs.txt

# ─── Entrypoint ────────────────────────────────────────────
ENTRYPOINT ["/app/entrypoint.sh"]