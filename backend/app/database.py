from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DB_DIR = Path(__file__).resolve().parent
DATABASE_URL = os.getenv("MLOPS_DATABASE_URL", f"sqlite:///{DB_DIR / 'mlops.db'}")


class Base(DeclarativeBase):
    pass


engine_options = {"future": True}
if DATABASE_URL.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}
engine = create_engine(DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
