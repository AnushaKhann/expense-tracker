import os
from sqlalchemy import create_engine

# Read the DATABASE_URL from environment variables
database_url = os.environ.get("DATABASE_URL")

if not database_url:
    raise Exception("❌ DATABASE_URL not set")

# Create SQLAlchemy engine
engine = create_engine(database_url)

# Try to connect
try:
    with engine.connect() as connection:
        print("✅ Successfully connected to the database!")
except Exception as e:
    print("❌ Failed to connect:", e)
