import unittest
from unittest.mock import Mock

from pipeline.config import load_firms
from pipeline.connectors import build_connector
from pipeline.connectors.errors import UnexpectedResponseError
from pipeline.connectors.latham_watkins import LathamWatkinsConnector


MA = "Mergers & Acquisitions"
GOVERNANCE = "Corporate Governance"


def row(slug, practice, role="Partner"):
    return {
        "clickUri": f"https://www.lw.com/en/people/{slug}",
        "raw": {
            "peopleformattedname": slug, "peoplebuckettitle": [role],
            "peopleoffices": ["London"], "peoplepractices": [practice],
        },
    }


def page(total, *rows):
    return Mock(**{"json.return_value": {
        "totalCount": total, "totalCountFiltered": total, "results": list(rows),
    }})


class LathamWatkinsTests(unittest.TestCase):
    def setUp(self):
        self.config = load_firms()["latham_watkins"]
        self.session = Mock()
        self.session.get.return_value.content = (
            b'<script>const accessToken = "test"; searchInterface.initialize({});</script>'
        )
        self.connector = LathamWatkinsConnector(
            "latham_watkins",
            {**self.config, "page_size": 2, "request_interval_seconds": 0},
            self.session,
        )

    def test_paginates_deduplicates_across_practices_and_reports_partial_scope(self):
        self.session.post.side_effect = [
            page(3, row("alex", MA), row("blake", MA)),
            page(3, row("casey", MA)),
            page(1, row("alex", GOVERNANCE)),
        ]

        result = self.connector.extract()

        self.assertEqual(result.expected_total, 3)
        self.assertEqual(result.pages_fetched, 3)
        self.assertTrue(result.extraction_complete)
        self.assertFalse(result.scope_verified)
        self.assertEqual(result.covered_practices, [MA, GOVERNANCE])
        self.assertEqual(result.records[0].practices, [MA, GOVERNANCE])
        self.assertEqual(result.records[0].offices, ["London"])
        self.assertEqual(
            [call.kwargs["json"]["firstResult"] for call in self.session.post.call_args_list],
            [0, 2, 0],
        )

    def test_rejects_duplicate_profiles_within_a_search(self):
        self.session.post.side_effect = [
            page(3, row("alex", MA), row("blake", MA)),
            page(3, row("alex", MA)),
        ]
        with self.assertRaisesRegex(UnexpectedResponseError, "duplicate profile"):
            self.connector.extract()

    def test_rejects_wrong_role(self):
        self.session.post.return_value = page(1, row("alex", MA, role="Counsel"))
        with self.assertRaisesRegex(UnexpectedResponseError, "unconfirmed partner"):
            self.connector.extract()

    def test_rejects_incomplete_batches(self):
        self.session.post.return_value = page(3, row("alex", MA))
        with self.assertRaisesRegex(UnexpectedResponseError, "inconsistent results"):
            self.connector.extract()

    def test_registered_for_expected_partial_publication(self):
        self.assertIsInstance(build_connector("latham_watkins", self.config), LathamWatkinsConnector)
        self.assertTrue(self.config["refresh_enabled"])
        self.assertTrue(self.config["publish_partial_scope"])
        self.assertTrue(self.config["expected_partial_scope"])
