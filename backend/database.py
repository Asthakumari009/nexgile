"""SQLite engine + session. One file, no connection pooling theatre."""
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "decarbx.db"
STORAGE_DIR = BASE_DIR.parent / "storage"

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    # ponytail: check_same_thread off is fine for a single-process demo;
    # a real deploy moves to Postgres and drops this.
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
