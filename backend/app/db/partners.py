import json
import sqlite3

from backend.app.db.office_labels import normalise_offices
from backend.app.schemas.partners import (
    PartnerDirectory,
    PartnerEntry,
    PartnerProfile,
    RosterChange,
    RosterCoverage,
)

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
        roster_offices = values.pop("roster_offices")
        roster_practices = values.pop("roster_practices")
        values["offices"] = normalise_offices(json.loads(values["offices"])) or normalise_offices(
            json.loads(roster_offices)
        )
        values["practices"] = json.loads(values["practices"]) or json.loads(roster_practices)
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
    changes = [
        RosterChange(kind="no_longer_listed", **dict(row))
        for row in connection.execute(
            """
            SELECT name, firm_name, no_longer_listed_at AS observed_at, source_url
            FROM partner_entries_all
            WHERE no_longer_listed_at IS NOT NULL
            """
        )
    ]
    return PartnerDirectory(
        records=records,
        coverage=RosterCoverage(
            verified_firm_count=verified_firm_count,
            partial_firm_count=partial_firm_count,
            target_firm_count=TARGET_FIRM_COUNT,
        ),
        changes=changes if verified_firm_count or changes else None,
    )


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
