from __future__ import annotations

import unittest

import requests

from pipeline.connectors.errors import ConnectorError
from pipeline.connectors.errors import UnexpectedResponseError
from pipeline.connectors.kirkland import KirklandConnector


CONFIG = {
    "directory_url": "https://www.kirkland.com/lawyers",
    "results_url": "https://www.kirkland.com/api/sitecore/ProfessionalsApi/Lawyers",
}


class KirklandConnectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connector = KirklandConnector("kirkland", CONFIG)

    def test_parses_partner_and_normalizes_profile_url(self) -> None:
        row = {
            "Name": "  Jane   Example ",
            "Position": "Partner",
            "Offices": [{"Name": "London"}, {"Name": "New York"}],
            "Url": "/lawyers/e/example-jane",
        }

        record = self.connector._parse_row(row, CONFIG["results_url"])

        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.name, "Jane Example")
        self.assertEqual(record.offices, ["London", "New York"])
        self.assertEqual(
            record.profile_url,
            "https://www.kirkland.com/lawyers/e/example-jane",
        )

    def test_excludes_non_partner(self) -> None:
        row = {
            "Name": "Alex Associate",
            "Position": "Associate",
            "Offices": ["London"],
            "Url": "/lawyers/a/alex-associate",
        }
        self.assertIsNone(self.connector._parse_row(row, CONFIG["results_url"]))

    def test_rejects_unknown_response_shape(self) -> None:
        with self.assertRaises(UnexpectedResponseError):
            self.connector._find_rows({"unexpected": []}, "A")

    def test_wraps_network_failure_as_connector_error(self) -> None:
        class FailingSession:
            def get(self, *args, **kwargs):
                raise requests.exceptions.RetryError("source returned repeated 500s")

        connector = KirklandConnector("kirkland", CONFIG, session=FailingSession())

        with self.assertRaisesRegex(ConnectorError, "letter A failed"):
            connector._fetch_letter(CONFIG["results_url"], "A")


if __name__ == "__main__":
    unittest.main()
