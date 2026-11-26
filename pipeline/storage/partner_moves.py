"""Pair roster observations and record reviewer-confirmed moves."""

import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlsplit


MATCH_WINDOW = timedelta(days=90)


def name_key(name: str) -> str:
    unaccented = "".join(
        char for char in unicodedata.normalize("NFKD", name.casefold())
        if not unicodedata.combining(char)
    )
    return " ".join(re.findall(r"\w+", unaccented))


def list_partner_moves(connection: sqlite3.Connection) -> list[dict]:
    if not connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'confirmed_partner_moves'"
    ).fetchone():
        return []
    rows = connection.execute(
        """
        SELECT e.*, c.evidence_url, c.effective_on, c.confirmed_at,
               c.addition_event_id AS confirmed_addition,
               a.departure_event_id AS confirmed_departure,
               NOT EXISTS (
                   SELECT 1 FROM partner_roster_events AS later
                   WHERE later.partner_entry_id = e.partner_entry_id AND later.event_id > e.event_id
               ) AS is_latest
        FROM partner_roster_events AS e
        LEFT JOIN confirmed_partner_moves AS c ON c.departure_event_id = e.event_id
        LEFT JOIN confirmed_partner_moves AS a ON a.addition_event_id = e.event_id
        WHERE e.kind IN ('newly_listed', 'no_longer_listed')
        """
    )
    events = {row["event_id"]: dict(row) for row in rows}
    additions = defaultdict(list)
    moves = []
    for event in events.values():
        if event["confirmed_addition"] is not None:
            moves.append(_move(event, events[event["confirmed_addition"]]))
        if event["kind"] == "newly_listed" and event["is_latest"] and event["confirmed_departure"] is None:
            additions[name_key(event["name"])].append(event)

    pairs = []
    for event in events.values():
        if event["kind"] != "no_longer_listed" or not event["is_latest"] or event["confirmed_addition"] is not None:
            continue
        key = name_key(event["name"])
        if len(key.split()) < 2:
            continue
        for addition in additions[key]:
            gap = abs(_event_date(event) - _event_date(addition))
            if event["firm_key"] != addition["firm_key"] and gap <= MATCH_WINDOW:
                pairs.append((event, addition))
    counts = Counter(event["event_id"] for pair in pairs for event in pair)
    moves.extend(_move(departure, addition) for departure, addition in pairs
                 if counts[departure["event_id"]] == counts[addition["event_id"]] == 1)
    return sorted(moves, key=lambda move: move["observed_at"], reverse=True)


def _event_date(event: dict) -> date:
    return date.fromisoformat(event["observed_at"][:10])


def _move(departure: dict, addition: dict) -> dict:
    return {
        "departure_event_id": departure["event_id"],
        "addition_event_id": addition["event_id"],
        "name": addition["name"],
        "from_firm": departure["firm_name"],
        "to_firm": addition["firm_name"],
        "observed_at": max(departure["observed_at"], addition["observed_at"]),
        "from_source_url": departure["source_url"],
        "to_source_url": addition["source_url"],
        "status": "confirmed" if departure["confirmed_at"] else "possible",
        "evidence_url": departure["evidence_url"],
        "effective_on": departure["effective_on"],
    }


def confirm_partner_move(connection: sqlite3.Connection, departure_id: int, addition_id: int,
                         evidence_url: str, effective_on: date | None) -> None:
    url = urlsplit(evidence_url)
    if url.scheme != "https" or not url.hostname or url.username or url.password:
        raise ValueError("Provide a public HTTPS source that identifies the partner and both firms.")
    if not any(
        move["status"] == "possible"
        and (move["departure_event_id"], move["addition_event_id"]) == (departure_id, addition_id)
        for move in list_partner_moves(connection)
    ):
        raise ValueError("Those event IDs do not identify a current possible move.")
    connection.execute(
        """
        INSERT INTO confirmed_partner_moves
            (departure_event_id, addition_event_id, evidence_url, confirmed_at, effective_on)
        VALUES (?, ?, ?, ?, ?)
        """,
        (departure_id, addition_id, evidence_url, datetime.now(timezone.utc).isoformat(),
         effective_on.isoformat() if effective_on else None),
    )
