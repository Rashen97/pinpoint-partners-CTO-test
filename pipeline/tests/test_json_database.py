from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pipeline.models import ExtractionResult, PartnerEntryInfo, PartnerProfileInfo
from pipeline.processing.identity import create_partner_entry_id
from pipeline.storage.json_database import JsonDatabase


def extraction(*, complete: bool = True, verified: bool = True) -> ExtractionResult:
    return ExtractionResult(
        firm_key="example_firm",
        records=[
            PartnerEntryInfo(
                firm_key="example_firm",
                firm_name="Example Firm",
                name="Alex Example",
                role="Partner",
                offices=["London"],
                practices=["Corporate"],
                profile_url="https://example.com/alex",
                source_url="https://example.com/directory",
                partner_entry_id=create_partner_entry_id(
                    "example_firm", "https://example.com/alex"
                ),
            )
        ],
        pages_fetched=1,
        extraction_complete=complete,
        scope_verified=verified,
        covered_practices=["Corporate"],
    )


class JsonDatabaseTests(unittest.TestCase):
    def test_saves_connector_and_unified_stage_documents(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database = JsonDatabase(Path(temp_dir))

            connector_path = database.save_connector_extraction(extraction())
            entries_path = database.save_partner_entries(extraction())

            connector_document = json.loads(connector_path.read_text(encoding="utf-8"))
            entries_document = json.loads(entries_path.read_text(encoding="utf-8"))
            self.assertEqual(connector_document["stage"], "connector_extraction")
            self.assertEqual(entries_document["stage"], "partner_entries")
            self.assertEqual(entries_document["record_count"], 1)
            self.assertEqual(entries_document["records"][0]["name"], "Alex Example")

    def test_unverified_refresh_cannot_replace_last_good_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database = JsonDatabase(Path(temp_dir))
            entries_path = database.save_partner_entries(extraction())
            original = entries_path.read_text(encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "unverified scope"):
                database.save_partner_entries(extraction(verified=False))

            self.assertEqual(entries_path.read_text(encoding="utf-8"), original)

    def test_incomplete_refresh_cannot_replace_last_good_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database = JsonDatabase(Path(temp_dir))
            entries_path = database.save_partner_entries(extraction())
            original = entries_path.read_text(encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "incomplete"):
                database.save_partner_entries(extraction(complete=False))

            self.assertEqual(entries_path.read_text(encoding="utf-8"), original)

    def test_saves_combined_dataset_for_verified_firms(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database = JsonDatabase(Path(temp_dir))
            first = extraction()
            second = extraction()
            second.firm_key = "second_firm"
            second.records = [
                PartnerEntryInfo(
                    firm_key="second_firm",
                    firm_name="Second Firm",
                    name="Blair Example",
                    role="Partner",
                    offices=["New York"],
                    practices=["Mergers and Acquisitions"],
                    profile_url="https://second.example/blair",
                    source_url="https://second.example/directory",
                    partner_entry_id=create_partner_entry_id(
                        "second_firm", "https://second.example/blair"
                    ),
                )
            ]

            combined_path = database.save_all_partner_entries([first, second])
            document = json.loads(combined_path.read_text(encoding="utf-8"))

            self.assertEqual(document["stage"], "all_partner_entries")
            self.assertEqual(document["record_count"], 2)
            self.assertEqual(document["firms"], ["example_firm", "second_firm"])
            loaded = database.load_all_partner_entries()
            self.assertEqual([item.firm_key for item in loaded], ["example_firm", "second_firm"])

    def test_combined_dataset_rejects_an_unverified_firm(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database = JsonDatabase(Path(temp_dir))
            with self.assertRaisesRegex(ValueError, "unverified firm"):
                database.save_all_partner_entries([extraction(verified=False)])

    def test_saves_combined_profile_stage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database = JsonDatabase(Path(temp_dir))
            profile = PartnerProfileInfo(
                firm_key="example_firm",
                name="Alex Example",
                profile_url="https://example.com/alex",
                role="Partner",
                offices=["London"],
                practices=["Corporate"],
                biography="Biography",
                phone_numbers=[],
                email=None,
                education=[],
                admissions=[],
                languages=[],
                source_checked_at="2026-11-18T00:00:00+00:00",
                content_hash="a" * 64,
                partner_entry_id=create_partner_entry_id(
                    "example_firm", "https://example.com/alex"
                ),
            )

            path = database.save_all_partner_profiles([profile], [])
            document = json.loads(path.read_text(encoding="utf-8"))

            self.assertEqual(document["stage"], "all_partner_profiles")
            self.assertEqual(document["profile_count"], 1)
            self.assertEqual(document["failure_count"], 0)


if __name__ == "__main__":
    unittest.main()
