from contextlib import closing
from dataclasses import replace
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from pipeline.models import ExtractionResult
from pipeline.profile_enrichment.connector import ConfiguredHtmlProfileConnector
from pipeline.storage.sqlite_database import SQLiteDatabase
from pipeline.tests.test_profile_connector import HTML, SOURCES, entry


class SQLiteRosterRemovalTests(unittest.TestCase):
    def test_verified_omission_preserves_profile_and_reappearance_reactivates(self):
        partner = entry()
        remaining = replace(
            partner, partner_entry_id="entry-456", profile_url="https://example.com/other"
        )
        profile = ConfiguredHtmlProfileConnector(SOURCES).parse(partner, HTML)
        full = ExtractionResult(
            partner.firm_key, [partner, remaining],
            extraction_complete=True, scope_verified=True,
        )
        reduced = replace(full, records=[remaining])

        with TemporaryDirectory() as directory:
            database = SQLiteDatabase(Path(directory) / "partners.db")
            database.save_all_partner_entries([full])
            database.save_all_partner_profiles([profile], [])

            with self.assertRaises(ValueError):
                database.save_all_partner_entries([replace(reduced, scope_verified=False)])
            self.assertCountEqual(database.load_all_partner_entries(), full.records)

            database.save_all_partner_entries([reduced])
            self.assertEqual(database.load_all_partner_entries(), [remaining])
            with closing(sqlite3.connect(database.path)) as connection:
                def removal_date():
                    return connection.execute(
                        "SELECT no_longer_listed_at FROM partner_entries_all "
                        "WHERE partner_entry_id = ?", (partner.partner_entry_id,)
                    ).fetchone()[0]

                removed_at = removal_date()
                self.assertIsNotNone(removed_at)
                database.save_all_partner_entries([reduced])
                self.assertEqual(removal_date(), removed_at)
                self.assertEqual(
                    connection.execute("SELECT content_hash FROM partner_profiles_all").fetchone(),
                    (profile.content_hash,),
                )
                database.save_all_partner_entries([full])
                self.assertIsNone(removal_date())
                self.assertCountEqual(database.load_all_partner_entries(), full.records)
