"""
database.py — SQLAlchemy database engine and session factory.
Creates the SQLite DB file and tables on first run.
"""

import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import StaticPool

from config import settings

# ---------------------------------------------------------------------------
# Ensure data/ directory exists
# ---------------------------------------------------------------------------
os.makedirs("data", exist_ok=True)

# ---------------------------------------------------------------------------
# Engine — SQLite with WAL mode for better concurrent reads
# ---------------------------------------------------------------------------
connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    poolclass=StaticPool,   # single connection pool → fine for SQLite
    echo=settings.DEBUG,
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Enable WAL journal mode and foreign keys on every new connection."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ---------------------------------------------------------------------------
# Declarative base
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Dependency — FastAPI dependency injection for DB sessions
# ---------------------------------------------------------------------------
def get_db():
    """Yield a DB session and ensure it's closed after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Init — called at startup to create all tables
# ---------------------------------------------------------------------------
def init_db():
    """Create all tables defined in models.py."""
    from models import SensorReading, Alert, SensorHealth  # noqa: F401
    Base.metadata.create_all(bind=engine)
