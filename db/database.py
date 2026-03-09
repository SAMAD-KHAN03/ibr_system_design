import logging
import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session

log = logging.getLogger(__name__)

# Convert URL for psycopg2
DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "postgresql://bra_user:bra_password@localhost:5432/bra_db",
).replace("postgresql+asyncpg://", "postgresql://")

engine = create_engine(
    DATABASE_URL,
    pool_size=15,
    max_overflow=20,
    pool_recycle=1800,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

def init_db():
    from db import models
    Base.metadata.create_all(bind=engine)
    log.info("Database tables initialized (Sync).")

@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()