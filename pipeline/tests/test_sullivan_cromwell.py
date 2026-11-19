from __future__ import annotations

import unittest

from pipeline.connectors.sullivan_cromwell import SullivanCromwellConnector


CONFIG = {
    "name": "Sullivan & Cromwell",
    "directory_url": "https://www.sullcrom.com/LawyerListing",
    "results_url": "https://search.example/select/",
    "partner_type_id": 25257,
    "page_size": 100,
    "practice_filters": [{"label": "Mergers & Acquisitions", "id": 69620}],
    "missing_practices": ["Corporate"],
}


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "response": {
                "numFound": 1,
                "docs": [
                    {
                        "id": "123",
                        "title": "Alex Example",
                        "custom_s_proftype": "Partner",
                        "custom_s_office_title": "New York",
                        "custom_s_url": "/Lawyers/Alex-Example",
                    }
                ],
            }
        }


class FakeSession:
    def get(self, *args, **kwargs):
        return FakeResponse()


class SullivanCromwellTests(unittest.TestCase):
    def test_extracts_m_and_a_but_marks_corporate_missing(self) -> None:
        result = SullivanCromwellConnector(
            "sullivan_cromwell", CONFIG, FakeSession()
        ).extract()

        self.assertEqual(len(result.records), 1)
        self.assertFalse(result.scope_verified)
        self.assertEqual(result.missing_practices, ["Corporate"])
        self.assertEqual(result.records[0].source_record_id, "123")
        self.assertEqual(
            result.records[0].profile_url,
            "https://www.sullcrom.com/Lawyers/Alex-Example",
        )


if __name__ == "__main__":
    unittest.main()
