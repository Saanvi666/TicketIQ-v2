import os
from collections.abc import Generator
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, declarative_base, sessionmaker

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ticketiq.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


Base = declarative_base()


def ensure_sqlite_columns(table) -> None:
    if engine.dialect.name != "sqlite":
        return

    existing_columns = {
        column["name"] for column in inspect(engine).get_columns(table.name)
    }
    missing_columns = [
        column
        for column in table.columns
        if column.name not in existing_columns
    ]

    if not missing_columns:
        return

    with engine.begin() as connection:
        for column in missing_columns:
            column_type = column.type.compile(dialect=engine.dialect)
            connection.exec_driver_sql(
                f"ALTER TABLE {table.name} ADD COLUMN {column.name} {column_type}"
            )


def remove_sqlite_columns(table, column_names: set[str]) -> None:
    if engine.dialect.name != "sqlite":
        return

    existing_columns = {
        column["name"] for column in inspect(engine).get_columns(table.name)
    }
    obsolete_columns = existing_columns.intersection(column_names)
    if not obsolete_columns:
        return

    with engine.begin() as connection:
        for column_name in sorted(obsolete_columns):
            connection.exec_driver_sql(
                f'ALTER TABLE "{table.name}" DROP COLUMN "{column_name}"'
            )


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
