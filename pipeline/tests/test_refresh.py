
import argparse
import io
import json
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


def roster(firm_key, slug):
    records = normalize_records([
        replace(
            entry(),
            firm_key=firm_key,
            profile_url=f"https://example.com/{slug}",
            partner_entry_id="",
        )
    ])
    return ExtractionResult(
        firm_key,
        records,
        extraction_complete=True,
        scope_verified=True,
    )


class RefreshTests(unittest.TestCase):

    def test_failed_firm_preserves_prior_roster_and_other_firm_updates(self):
        first = roster("first", "original")
        second = roster("second", "retained")
        updated = roster("first", "new")
        partial = replace(
            roster("third", "partial"),
            scope_verified=False,
        )

        connectors = [
            Mock(extract=Mock(return_value=updated)),
            Mock(extract=Mock(
                side_effect=ConnectorError("source unavailable")
            )),
            Mock(extract=Mock(return_value=partial)),
        ]

        firms = {
            key: {"refresh_enabled": True}
            for key in ("first", "second")
        }

        firms["third"] = {
            "refresh_enabled": True,
            "publish_partial_scope": True,
            "expected_partial_scope": True,
        }

        args = argparse.Namespace(
            firm=None,
            include_unverified_scope=False,
            publish_partial=False,
            directory_only=True,
            profile_limit=None,
        )

        with TemporaryDirectory() as directory:
            database = SQLiteDatabase(Path(directory) / "partners.db")
            database.save_all_partner_entries([first, second])

            with (
                patch.object(refresh, "parse_args", return_value=args),
                patch.object(refresh, "load_firms", return_value=firms),
                patch.object(refresh, "SQLiteDatabase", return_value=database),
                patch.object(refresh, "build_connector", side_effect=connectors),
                redirect_stdout(io.StringIO()) as output,
                redirect_stderr(io.StringIO()) as errors,
            ):
                self.assertEqual(refresh.main(), 1)

            self.assertCountEqual(
                database.load_all_partner_entries(),
                updated.records + second.records + partial.records,
            )

            self.assertEqual(
                json.loads(output.getvalue())["summary"]["third"]["status"],
                "partial",
            )

            self.assertIn("second: failed", errors.getvalue())
            self.assertNotIn("third:", errors.getvalue())

    def test_unexpected_partial_scope_preserves_roster_and_reports_failure(self):
        previous = roster("first", "original")
        partial = replace(
            roster("first", "new"),
            scope_verified=False,
        )

        firms = {
            "first": {
                "refresh_enabled": True,
                "publish_partial_scope": True,
                "expected_partial_scope": False,
            }
        }

        args = argparse.Namespace(
            firm=None,
            include_unverified_scope=False,
            publish_partial=False,
            directory_only=True,
            profile_limit=None,
        )

        with TemporaryDirectory() as directory:
            database = SQLiteDatabase(Path(directory) / "partners.db")
            database.save_all_partner_entries([previous])

            with (
                patch.object(refresh, "parse_args", return_value=args),
                patch.object(refresh, "load_firms", return_value=firms),
                patch.object(refresh, "SQLiteDatabase", return_value=database),
                patch.object(
                    refresh,
                    "build_connector",
                    return_value=Mock(
                        extract=Mock(return_value=partial)
                    ),
                ),
                redirect_stdout(io.StringIO()) as output,
                redirect_stderr(io.StringIO()) as errors,
            ):
                self.assertNotEqual(refresh.main(), 0)

            self.assertCountEqual(
                database.load_all_partner_entries(),
                previous.records + partial.records,
            )

            self.assertEqual(
                json.loads(output.getvalue())["summary"]["first"]["status"],
                "unexpected_partial",
            )

            self.assertIn(
                "first: unexpected_partial",
                errors.getvalue(),
            )
