# ~/v4-iot-pipeline/2b-transform-server/app/database/base.py
# Version: 0.1.0 - 2025-07-23 15:20 UTC
# Changelog:
# - Initial creation of declarative Base for SQLAlchemy models

from sqlalchemy.orm import declarative_base

Base = declarative_base()
