"""Persist refresh stages in SQLite."""

from __future__ import annotations

import json
import re
import sqlite3
from contextlib import closing, contextmanager
from dataclasses import asdict, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator

from pipeline.models import ExtractionResult, PartnerEntryInfo, PartnerProfileInfo

if TYPE_CHECKING:
    from pipeline.profile_enrichment.service import ProfileEnrichmentFailure

DATABASE_DIR = Path(__file__).resolve().parents[2] / "database"
ENTRY_COLUMNS = tuple(field.name for field in fields(PartnerEntryInfo))
ENTRY_SELECT = ", ".join(ENTRY_COLUMNS)
PROFILE_COLUMNS = tuple(
    field.name for field in fields(PartnerProfileInfo)
    if field.name not in {"firm_key", "name", "profile_url"}
)


class SQLiteDatabase:
    def __init__(self, path: Path = DATABASE_DIR / "partners.db") -> None:
        self.path = path
        with self._transaction() as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            for migration in sorted((DATABASE_DIR / "migrations").glob("*.sql")):
                number = int(migration.name.split("_", 1)[0])
                if number <= version:
                    continue
                statement = ""
                for line in migration.read_text(encoding="utf-8").splitlines(keepends=True):
                    statement += line
                    if sqlite3.complete_statement(statement):
                        connection.execute(statement)
                        statement = ""
                if statement.strip():
                    raise ValueError(f"Incomplete SQL statement in {migration}")
                connection.execute(f"PRAGMA user_version = {number}")

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN IMMEDIATE")
            yield connection

    def save_connector_extraction(self, result: ExtractionResult) -> str:
        table = self._firm_table("scraped_raw", result.firm_key)
        metadata = {
            "firm_key": result.firm_key,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "pages_fetched": result.pages_fetched,
            "expected_total": result.expected_total,
            "extraction_complete": result.extraction_complete,
            "scope_verified": result.scope_verified,
            "covered_practices": result.covered_practices,
            "missing_practices": result.missing_practices,
            "warnings": result.warnings,
        }
        with self._transaction() as connection:
            self._replace_firm_table(connection, table, result.records)
            connection.execute(
                "DELETE FROM scraped_raw_runs WHERE firm_key = ?", (result.firm_key,)
            )
            self._insert(connection, "scraped_raw_runs", tuple(metadata), [metadata])
        return table

    def save_partner_entries(self, result: ExtractionResult) -> str:
        self._validate_roster(result)
        table = self._firm_table("partner_entries", result.firm_key)
        with self._transaction() as connection:
            self._replace_firm_table(connection, table, result.records)
        return table

    def save_all_partner_entries(self, results: list[ExtractionResult]) -> str:
        if not results:
            raise ValueError("Cannot save an empty combined roster")
        for result in results:
            self._validate_roster(result)
        records = [
            asdict(record) for result in results for record in result.records
        ]
        with self._transaction() as connection:
            connection.execute(
                f"CREATE TEMP TABLE next_entries AS SELECT {ENTRY_SELECT} "
                "FROM partner_entries_all WHERE 0"
            )
            self._insert(connection, "next_entries", ENTRY_COLUMNS, records)
            listed_at = datetime.now(timezone.utc).isoformat()
            self._record_roster_events(connection, listed_at)
            connection.executemany(
                """
                UPDATE partner_entries_all
                SET no_longer_listed_at = ?
                WHERE firm_key = ?
                  AND no_longer_listed_at IS NULL
                  AND partner_entry_id NOT IN (SELECT partner_entry_id FROM next_entries)
                """,
                [(listed_at, result.firm_key) for result in results],
            )
            self._insert(
                connection,
                "partner_entries_all",
                (*ENTRY_COLUMNS, "no_longer_listed_at", "scope_verified"),
                [dict(record, no_longer_listed_at=None, scope_verified=True) for record in records],
                upsert=True,
            )
            connection.execute(
                "INSERT OR IGNORE INTO firm_roster_baselines (firm_key) "
                "SELECT DISTINCT firm_key FROM next_entries"
            )
        return "partner_entries_all"

    @staticmethod
    def _record_roster_events(connection: sqlite3.Connection, listed_at: str) -> None:
        connection.execute(
            """
            INSERT INTO partner_roster_events (
                partner_entry_id, firm_key, firm_name, name, kind, observed_at, source_url
            )
            SELECT incoming.partner_entry_id, incoming.firm_key, incoming.firm_name, incoming.name,
                   CASE WHEN prior.scope_verified = 1 THEN 'relisted' ELSE 'newly_listed' END,
                   ?, incoming.profile_url
            FROM next_entries AS incoming
            JOIN firm_roster_baselines AS baseline ON baseline.firm_key = incoming.firm_key
            LEFT JOIN partner_entries_all AS prior ON prior.partner_entry_id = incoming.partner_entry_id
            WHERE prior.scope_verified IS NOT 1 OR prior.no_longer_listed_at IS NOT NULL
            UNION ALL
            SELECT prior.partner_entry_id, prior.firm_key, prior.firm_name, prior.name,
                   'no_longer_listed', ?, prior.source_url
            FROM partner_entries_all AS prior
            WHERE prior.scope_verified = 1 AND prior.no_longer_listed_at IS NULL
              AND prior.firm_key IN (SELECT firm_key FROM next_entries)
              AND prior.partner_entry_id NOT IN (SELECT partner_entry_id FROM next_entries)
            """,
            (listed_at, listed_at),
        )

    def save_partial_partner_entries(self, result: ExtractionResult) -> str:
        if result.scope_verified or not result.extraction_complete or not result.records:
            raise ValueError("Partial import requires a complete extraction of a limited scope")
        if any(
            not record.partner_entry_id or record.firm_key != result.firm_key
            for record in result.records
        ):
            raise ValueError("Missing or invalid roster records")
        with self._transaction() as connection:
            self._insert(
                connection,
                "partner_entries_all",
                (*ENTRY_COLUMNS, "scope_verified"),
                [dict(asdict(record), scope_verified=False) for record in result.records],
                upsert=True,
            )
        return "partner_entries_all"

    def load_all_partner_entries(self) -> list[PartnerEntryInfo]:
        with closing(sqlite3.connect(self.path)) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f"SELECT {ENTRY_SELECT} FROM partner_entries_all "
                "WHERE no_longer_listed_at IS NULL ORDER BY firm_key, name COLLATE NOCASE"
            ).fetchall()
        entries = []
        for row in rows:
            values = dict(row)
            values["offices"] = json.loads(values["offices"])
            values["practices"] = json.loads(values["practices"])
            entries.append(PartnerEntryInfo(**values))
        return entries

    def save_all_partner_profiles(
        self,
        profiles: list[PartnerProfileInfo],
        failures: list[ProfileEnrichmentFailure],
        *,
        firm_key: str | None = None,
    ) -> str:
        with self._transaction() as connection:
            current_ids = {
                row[0] for row in connection.execute(
                    "SELECT partner_entry_id FROM partner_entries_all "
                    "WHERE no_longer_listed_at IS NULL"
                )
            }
            records = [asdict(profile) for profile in profiles if profile.partner_entry_id in current_ids]
            self._insert(connection, "partner_profiles_all", PROFILE_COLUMNS, records, upsert=True)
            if firm_key is None:
                connection.execute("DELETE FROM partner_profile_failures_all")
            else:
                connection.execute(
                    "DELETE FROM partner_profile_failures_all WHERE firm_key = ?", (firm_key,)
                )
            self._insert(
                connection,
                "partner_profile_failures_all",
                ("firm_key", "profile_url", "error"),
                [asdict(failure) for failure in failures],
            )
        return "partner_profiles_all"

    @staticmethod
    def _firm_table(prefix: str, firm_key: str) -> str:
        if not re.fullmatch(r"[a-z0-9_]+", firm_key) or firm_key in {"all", "runs"}:
            raise ValueError(f"Invalid firm key: {firm_key!r}")
        return f"{prefix}_{firm_key}"

    @staticmethod
    def _validate_roster(result: ExtractionResult) -> None:
        if not result.extraction_complete or not result.scope_verified:
            raise ValueError(f"Cannot save incomplete or unverified roster: {result.firm_key}")
        if not result.records or any(
            not record.partner_entry_id or record.firm_key != result.firm_key
            for record in result.records
        ):
            raise ValueError(f"Missing or invalid roster records: {result.firm_key}")

    def _replace_firm_table(
        self, connection: sqlite3.Connection, table: str, records: list[PartnerEntryInfo]
    ) -> None:
        connection.execute(
            f"CREATE TABLE IF NOT EXISTS {table} AS SELECT {ENTRY_SELECT} "
            "FROM partner_entries_all WHERE 0"
        )
        connection.execute(f"DELETE FROM {table}")
        self._insert(connection, table, ENTRY_COLUMNS, [asdict(record) for record in records])

    @staticmethod
    def _insert(
        connection: sqlite3.Connection,
        table: str,
        columns: tuple[str, ...],
        records: list[dict[str, Any]],
        *,
        upsert: bool = False,
    ) -> None:
        names = ", ".join(columns)
        placeholders = ", ".join("?" for _ in columns)
        sql = f"INSERT INTO {table} ({names}) VALUES ({placeholders})"
        if upsert:
            updates = ", ".join(
                f"{column} = excluded.{column}" for column in columns if column != "partner_entry_id"
            )
            if table == "partner_profiles_all":
                updates += (
                    " WHERE excluded.content_hash IS NOT partner_profiles_all.content_hash"
                    " AND excluded.source_checked_at >= partner_profiles_all.source_checked_at"
                )
            elif table == "partner_entries_all" and "no_longer_listed_at" not in columns:
                updates += " WHERE partner_entries_all.scope_verified = 0"
            sql += f" ON CONFLICT (partner_entry_id) DO UPDATE SET {updates}"
        connection.executemany(
            sql,
            (
                tuple(
                    json.dumps(record[column], ensure_ascii=False)
                    if isinstance(record[column], list) else record[column]
                    for column in columns
                )
                for record in records
            ),
        )
