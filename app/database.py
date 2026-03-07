from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "nutrition.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


SQLITE_COLUMN_MIGRATIONS: dict[str, dict[str, str]] = {
    "foods": {
        "carbs_per_100g": "ALTER TABLE foods ADD COLUMN carbs_per_100g REAL NOT NULL DEFAULT 0",
        "fiber_per_100g": "ALTER TABLE foods ADD COLUMN fiber_per_100g REAL NOT NULL DEFAULT 0",
    },
    "meals": {
        "total_carbs": "ALTER TABLE meals ADD COLUMN total_carbs REAL NOT NULL DEFAULT 0",
        "total_fiber": "ALTER TABLE meals ADD COLUMN total_fiber REAL NOT NULL DEFAULT 0",
    },
    "meal_items": {
        "carbs": "ALTER TABLE meal_items ADD COLUMN carbs REAL NOT NULL DEFAULT 0",
        "fiber": "ALTER TABLE meal_items ADD COLUMN fiber REAL NOT NULL DEFAULT 0",
    },
}


def _apply_sqlite_schema_updates() -> None:
    if not DB_PATH.exists():
        return

    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.cursor()
        for table_name, columns in SQLITE_COLUMN_MIGRATIONS.items():
            existing_columns = {
                row[1]
                for row in cursor.execute(f"PRAGMA table_info({table_name})").fetchall()
            }
            for column_name, statement in columns.items():
                if column_name not in existing_columns:
                    cursor.execute(statement)
        connection.commit()


def create_db_and_tables() -> None:
    # Ensure model metadata is loaded before create_all.
    from app import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    _apply_sqlite_schema_updates()


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
