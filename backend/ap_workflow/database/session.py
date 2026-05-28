"""Database session management for AP Workflow Agent."""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from ap_workflow.core.config import settings

# Create engine with connection pooling
# Force IPv4 by using socket options
engine = create_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args={
        "options": "-c connect_timeout=10",
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
