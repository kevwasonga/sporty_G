from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

_SQLITE_ADD_COLUMN = [
    # (table, column, DDL) — tiny idempotent migrations for existing DBs.
    (
        "registrations",
        "manual_sms_select",
        "ALTER TABLE registrations ADD COLUMN manual_sms_select BOOLEAN NOT NULL DEFAULT 0",
    ),
]


class Base(DeclarativeBase):
    pass


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    from . import models  # noqa: F401  (register tables)

    Base.metadata.create_all(bind=engine)

    # Existing databases are missing newer columns; backfill them idempotently.
    insp = inspect(engine)
    existing = {t: {c["name"] for c in insp.get_columns(t)} for t in insp.get_table_names()}
    with engine.begin() as conn:
        for table, column, ddl in _SQLITE_ADD_COLUMN:
            if table in existing and column not in existing[table] and settings.database_url.startswith("sqlite"):
                conn.execute(text(ddl))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()