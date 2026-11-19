import sqlite3
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

from pipeline.storage.sqlite_database import DATABASE_DIR

DATABASE_PATH = DATABASE_DIR / "partners.db"


def open_database(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(
        f"{path.resolve().as_uri()}?mode=ro",
        uri=True,
        check_same_thread=False,
    )
    connection.row_factory = sqlite3.Row
    return connection


def get_database() -> Iterator[sqlite3.Connection]:
    with closing(open_database(DATABASE_PATH)) as connection, connection:
        connection.execute("BEGIN")
        yield connection
