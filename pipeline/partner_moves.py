"""List possible partner moves and record confirmations after source review."""

import argparse
import json
import sqlite3
from contextlib import closing
from datetime import date

from pipeline.storage.partner_moves import confirm_partner_move, list_partner_moves
from pipeline.storage.sqlite_database import SQLiteDatabase


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="Show possible and confirmed moves with event IDs")
    confirm = commands.add_parser("confirm", help="Confirm a match after reviewing a public source")
    confirm.add_argument("departure_event_id", type=int)
    confirm.add_argument("addition_event_id", type=int)
    confirm.add_argument("--evidence-url", required=True)
    confirm.add_argument("--effective-on", type=date.fromisoformat)
    confirm.add_argument("--reviewed", action="store_true", required=True,
                         help="Attest that the source identifies the partner and both firms")
    args = parser.parse_args()
    database = SQLiteDatabase()
    with closing(sqlite3.connect(database.path)) as connection, connection:
        connection.row_factory = sqlite3.Row
        if args.command == "list":
            print(json.dumps(list_partner_moves(connection), indent=2))
            return
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN IMMEDIATE")
        try:
            confirm_partner_move(
                connection, args.departure_event_id, args.addition_event_id,
                args.evidence_url, args.effective_on,
            )
        except ValueError as exc:
            parser.error(str(exc))
    print("Move confirmed.")


if __name__ == "__main__":
    main()
