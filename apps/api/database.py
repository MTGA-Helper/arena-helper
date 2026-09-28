import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

# Default to a reliable SQLite database file if DATABASE_URL is not set
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./arena.db")

# Create a clean sync engine with check_same_thread=False for SQLite compatibility
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, echo=False, future=True, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL, echo=False, future=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
