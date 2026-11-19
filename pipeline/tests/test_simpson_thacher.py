from __future__ import annotations

import unittest

from pipeline.connectors.simpson_thacher import SimpsonThacherConnector


CONFIG = {
    "name": "Simpson Thacher & Bartlett",
    "directory_url": "https://www.stblaw.com/our-team",
    "results_url": "https://www.stblaw.com/team",
    "records_key": "TeamModels",
    "total_key": "total",
    "page_size": 100,
    "page_filter_type": "PracticeArea",
    "practice_page_filters": [
        {"label": "Corporate", "id": "corporate-id"},
        {"label": "Mergers and Acquisitions", "id": "ma-id"},
    ],
    "form_params": {"position": "partner-id"},
}


class FakeResponse:
    def __init__(self, practice_id: str) -> None:
        self.practice_id = practice_id

    def raise_for_status(self):
        return None

    def json(self):
        name = "Shared Partner" if self.practice_id == "ma-id" else "Corporate Partner"
        slug = "shared-partner" if self.practice_id == "ma-id" else "corporate-partner"
        return {
            "total": 1,
            "TeamModels": [
                {
                    "FullName": name,
                    "Role": "Partner",
                    "Office": "London",
                    "PracticeFocuses": [{"Text": "Corporate"}],
                    "UrlName": slug,
                }
            ],
        }


class FakeSession:
    def __init__(self) -> None:
        self.headers = {}

    def post(self, url, data, timeout):
        return FakeResponse(data["pageFilterId"])


class SimpsonThacherTests(unittest.TestCase):
    def test_extracts_both_verified_practice_pages(self) -> None:
        result = SimpsonThacherConnector(
            "simpson_thacher", CONFIG, FakeSession()
        ).extract()

        self.assertTrue(result.scope_verified)
        self.assertEqual(result.pages_fetched, 2)
        self.assertEqual(len(result.records), 2)
        self.assertEqual(
            result.covered_practices,
            ["Corporate", "Mergers and Acquisitions"],
        )

    def test_preserves_double_hyphen_slug(self) -> None:
        connector = SimpsonThacherConnector(
            "simpson_thacher", CONFIG, FakeSession()
        )
        record = connector._parse_row(
            {
                "FullName": "Adam S. Aderton",
                "Role": "Partner",
                "Office": "New York",
                "PracticeFocuses": [],
                "UrlName": "adam-s--aderton",
            },
            CONFIG["results_url"],
            "Corporate",
        )
        self.assertTrue(record.profile_url.endswith("/adam-s--aderton"))


if __name__ == "__main__":
    unittest.main()
