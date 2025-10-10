#!/bin/bash
export TRANSFORM_DB_HOST=10.44.1.12
export TRANSFORM_DB_USER=iotuser
export TRANSFORM_DB_PASSWORD=secret
export TRANSFORM_DB_NAME=transform_db
export TRANSFORM_DB_INTERNAL_PORT=5432
export PYTHONPATH=/app
export LC_ALL=C.UTF-8
export LANG=C.UTF-8
cd /app
exec "$@"
