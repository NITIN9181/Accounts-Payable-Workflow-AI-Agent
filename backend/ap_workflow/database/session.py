"""Database session management for AP Workflow Agent."""

from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
import time

from ap_workflow.core.config import settings

# Use NullPool for cloud deployments to avoid connection pooling issues
engine = create_engine(
    settings.database_url,
    poolclass=NullPool,  # Disable connection pooling for cloud
    connect_args={
        "options": "-c connect_timeout=30",
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
    },
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create declarative base
Base = declarative_base()


def get_session():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# FastAPI dependency alias used by route modules
get_db = get_session
