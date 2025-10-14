# database/chirpstack_connection.py
# ChirpStack database connection
# Version: 1.0.0 - 2025-10-13

import os
from urllib.parse import quote_plus
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

# ChirpStack uses the same host but different database
DB_HOST = os.environ.get("TRANSFORM_DB_HOST", "parking-postgres")
DB_PORT = os.environ.get("TRANSFORM_DB_INTERNAL_PORT", "5432")
DB_USER = os.environ.get("TRANSFORM_DB_USER", "parking_user")
DB_PASSWORD = os.environ.get("TRANSFORM_DB_PASSWORD", "")

# URL-encode credentials
DB_USER_ENCODED = quote_plus(DB_USER)
DB_PASSWORD_ENCODED = quote_plus(DB_PASSWORD)

# ChirpStack database connection
CHIRPSTACK_DATABASE_URL = f"postgresql://{DB_USER_ENCODED}:{DB_PASSWORD_ENCODED}@{DB_HOST}:{DB_PORT}/chirpstack"
chirpstack_engine = create_engine(CHIRPSTACK_DATABASE_URL, echo=False)
ChirpStackSessionLocal = sessionmaker(bind=chirpstack_engine, expire_on_commit=False)

# Dependency for FastAPI
def get_chirpstack_db():
    db = ChirpStackSessionLocal()
    try:
        yield db
    finally:
        db.close()
