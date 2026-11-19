"""SQLite connection and schema initialization."""

from __future__ import annotations

import sqlite3
from pathlib import Path


DEFAULT_DATABASE_PATH = Path(__file__).parents[1] / "partners.db"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect(path: Path = DEFAULT_DATABASE_PATH) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
