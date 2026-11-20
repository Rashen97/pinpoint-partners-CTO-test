import unittest
from unittest.mock import Mock

from pipeline.config import load_firms
from pipeline.connectors import build_connector
from pipeline.connectors.errors import UnexpectedResponseError
from pipeline.connectors.skadden import SkaddenConnector
from pipeline.profile_enrichment.config import load_profile_sources
from pipeline.profile_enrichment.connector import ConfiguredHtmlProfileConnector


def row(slug, title="Partner", retired=False):
    return {
        "Name": slug, "ID": slug, "Url": f"/professionals/a/{slug}", "Level": title,
        "PrimaryOffice": {"Name": "London"}, "PrimaryPractice": "Private Equity",
        "IsRetiredPartner": retired, "IsDeceased": False,
    }


class SkaddenTests(unittest.TestCase):
    def setUp(self):
        self.config = load_firms()["skadden"]
        self.session = Mock()
        self.connector = SkaddenConnector(
            "skadden", {**self.config, "request_interval_seconds": 0}, self.session,
        )

    def batch(self, rows, *, more, total=3, include_role=True):
        ids = [self.config["practice_id"]]
        if include_role:
            ids.append(self.config["partner_position_id"])
        return Mock(url=self.config["results_url"], **{
            "json.return_value": {
                "ResultCount": total, "HasMoreResults": more, "SearchResults": rows,
                "SearchFilters": {
                    "AllSelectedFilters": [{"ID": value, "IsSelected": True} for value in ids],
                },
            },
        })

    def test_uses_returned_batch_length_and_preserves_partner_titles(self):
        self.session.get.side_effect = [
            self.batch([row("alex")], more=True),
            self.batch([row("blake", "<em>Bengoshi</em> Partner"), row("casey")], more=False),
        ]
        result = self.connector.extract()
        offsets = [call.kwargs["params"]["skip"] for call in self.session.get.call_args_list]
        self.assertEqual(offsets, [0, 1])
        self.assertTrue(result.extraction_complete)
        self.assertFalse(result.scope_verified)
        self.assertEqual(result.expected_total, 3)
        self.assertEqual(result.records[1].role, "Bengoshi Partner")
        self.assertEqual(result.records[1].offices, ["London"])
        self.assertEqual(result.records[1].practices, ["Mergers and Acquisitions", "Private Equity"])

        profile_parser = ConfiguredHtmlProfileConnector(load_profile_sources(), self.session)
        profile = profile_parser.parse(result.records[0], """
            <h1 class="profile-header-name">alex</h1>
            <section id="about"><div class="overview-wrapper"><p>Advises on acquisitions.</p></div></section>
        """)
        self.assertEqual(profile.biography, "Advises on acquisitions.")

    def test_rejects_repeated_profiles(self):
        self.session.get.side_effect = [
            self.batch([row("alex")], more=True),
            self.batch([row("alex"), row("casey")], more=False),
        ]
        with self.assertRaisesRegex(UnexpectedResponseError, "duplicate profile"):
            self.connector.extract()

    def test_rejects_missing_role_filter(self):
        self.session.get.return_value = self.batch([row("alex")], more=False, include_role=False)
        with self.assertRaisesRegex(UnexpectedResponseError, "did not confirm"):
            self.connector.extract()

    def test_rejects_premature_end(self):
        self.session.get.return_value = self.batch([row("alex")], more=False)
        with self.assertRaisesRegex(UnexpectedResponseError, "continuation disagreed"):
            self.connector.extract()

    def test_rejects_retired_partner(self):
        self.session.get.return_value = self.batch([row("alex", retired=True)], more=False, total=1)
        with self.assertRaisesRegex(UnexpectedResponseError, "active partner"):
            self.connector.extract()

    def test_registered_for_expected_partial_publication(self):
        self.assertIsInstance(build_connector("skadden", self.config), SkaddenConnector)
        self.assertTrue(self.config["refresh_enabled"])
        self.assertTrue(self.config["publish_partial_scope"])
        self.assertTrue(self.config["expected_partial_scope"])
