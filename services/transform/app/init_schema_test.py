# init_schema_test.py
# Version: 0.1.0 - 2025-07-18 15:15 UTC

from models import Base
from database.connections import engine

if __name__ == "__main__":
    print("🔧 Creating all tables for transform schema...")
    Base.metadata.create_all(bind=engine)
    print("✅ Done.")
