import json
import sqlite3

from backend.app.schemas.partners import (
    PartnerDirectory,
    PartnerEntry,
    PartnerMove,
    PartnerProfile,
    RosterChange,
    RosterCoverage,
)
from pipeline.storage.partner_moves import list_partner_moves

TARGET_FIRM_COUNT = 15


def list_directory(connection: sqlite3.Connection) -> PartnerDirectory:
    rows = connection.execute(
        """
        SELECT p.partner_entry_id, e.firm_key, e.firm_name, e.name,
               COALESCE(NULLIF(p.role, ''), e.role) AS role,
               p.offices, p.practices, e.profile_url, e.scope_verified,
               e.offices AS roster_offices, e.practices AS roster_practices
        FROM partner_profiles_all AS p
        JOIN partner_entries_all AS e ON e.partner_entry_id = p.partner_entry_id
        WHERE e.no_longer_listed_at IS NULL
        ORDER BY e.name COLLATE NOCASE, e.firm_key, p.partner_entry_id
        """
    )
    records = []
    for row in rows:
        values = dict(row)
        for field in ("offices", "practices"):
            roster_value = values.pop(f"roster_{field}")
            values[field] = json.loads(values[field]) or json.loads(roster_value)
        records.append(PartnerEntry.model_validate(values))

    verified_firm_count, partial_firm_count = connection.execute(
        """
        SELECT COUNT(DISTINCT CASE WHEN scope_verified = 1 THEN firm_key END),
               COUNT(DISTINCT firm_key) -
               COUNT(DISTINCT CASE WHEN scope_verified = 1 THEN firm_key END)
        FROM partner_entries_all
        WHERE no_longer_listed_at IS NULL
        """
    ).fetchone()
    changes = _list_roster_changes(connection)
    return PartnerDirectory(
        records=records,
        coverage=RosterCoverage(
            verified_firm_count=verified_firm_count,
            partial_firm_count=partial_firm_count,
            target_firm_count=TARGET_FIRM_COUNT,
        ),
        changes=changes if verified_firm_count or changes else None,
        moves=[PartnerMove.model_validate(move) for move in list_partner_moves(connection)],
    )


def _list_roster_changes(connection: sqlite3.Connection) -> list[RosterChange]:
    if connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'partner_roster_events'"
    ).fetchone():
        rows = connection.execute(
            """
            SELECT name, firm_name, kind, observed_at, source_url
            FROM partner_roster_events
            ORDER BY observed_at DESC, event_id DESC
            """
        )
    else:
        rows = connection.execute(
            """
            SELECT name, firm_name, 'no_longer_listed' AS kind,
                   no_longer_listed_at AS observed_at, source_url
            FROM partner_entries_all
            WHERE no_longer_listed_at IS NOT NULL
            """
        )
    return [RosterChange(**dict(row)) for row in rows]


def find_profile(connection: sqlite3.Connection, partner_entry_id: str) -> PartnerProfile | None:
    row = connection.execute(
        """
        SELECT p.biography, p.email, p.phone_numbers, p.education,
               p.admissions, p.languages, p.source_checked_at
        FROM partner_profiles_all AS p
        JOIN partner_entries_all AS e ON e.partner_entry_id = p.partner_entry_id
        WHERE p.partner_entry_id = ? AND e.no_longer_listed_at IS NULL
        """,
        (partner_entry_id,),
    ).fetchone()
    if row is None:
        return None

    values = dict(row)
    for field in ("phone_numbers", "education", "admissions", "languages"):
        values[field] = json.loads(values[field])
    return PartnerProfile.model_validate(values)
