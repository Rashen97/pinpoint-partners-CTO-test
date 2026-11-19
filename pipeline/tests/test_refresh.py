import argparse
import io
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from pipeline import refresh
from pipeline.connectors.errors import ConnectorError
from pipeline.models import ExtractionResult
from pipeline.processing.normalize import normalize_records
from pipeline.storage.sqlite_database import SQLiteDatabase
from pipeline.tests.test_profile_connector import entry


class RefreshTests(unittest.TestCase):
    def test_failed_firm_preserves_prior_roster_and_other_firm_updates(self):
        def roster(firm_key, slug):
            records = normalize_records([
                replace(
                    entry(), firm_key=firm_key, profile_url=f"https://example.com/{slug}",
                    partner_entry_id="",
                )
            ])
            return ExtractionResult(firm_key, records, extraction_complete=True, scope_verified=True)

        first = roster("first", "original")
        second = roster("second", "retained")
        updated = roster("first", "new")
        connectors = [
            Mock(extract=Mock(return_value=updated)),
            Mock(extract=Mock(side_effect=ConnectorError("source unavailable"))),
        ]
        firms = {key: {"refresh_enabled": True} for key in ("first", "second")}
        args = argparse.Namespace(
            firm=None, include_unverified_scope=False, directory_only=True, profile_limit=None
        )

        with TemporaryDirectory() as directory:
            database = SQLiteDatabase(Path(directory) / "partners.db")
            database.save_all_partner_entries([first, second])
            with (
                patch.object(refresh, "parse_args", return_value=args),
                patch.object(refresh, "load_firms", return_value=firms),
                patch.object(refresh, "SQLiteDatabase", return_value=database),
                patch.object(refresh, "build_connector", side_effect=connectors),
                redirect_stdout(io.StringIO()),
                redirect_stderr(io.StringIO()) as errors,
            ):
                self.assertEqual(refresh.main(), 1)

            self.assertCountEqual(
                database.load_all_partner_entries(), updated.records + second.records
            )
            self.assertIn("second: failed", errors.getvalue())
