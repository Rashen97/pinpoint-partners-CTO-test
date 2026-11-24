import unittest
from unittest.mock import Mock

from pipeline.config import load_firms
from pipeline.connectors import build_connector
from pipeline.connectors.errors import UnexpectedResponseError
from pipeline.connectors.paul_hastings import PaulHastingsConnector
from pipeline.profile_enrichment.service import enrich_entries


MA = "Mergers & Acquisitions"
CAPITAL_MARKETS = "Capital Markets"


def row(slug, practice, title="Partner"):
    return {
        "ph_content_type": "Professional",
        "ph_navigation_title": slug,
        "ph_professional_title_position": title,
        "ph_nested_practice_areas": [practice],
        "ph_nested_offices": ["London"],
        "ph_teaser": "Advises on transactions.",
        "url": f"https://www.paulhastings.com/professionals/{slug}",
    }


def page(total, offset, limit, *rows):
    return Mock(**{"json.return_value": {"widgets": [{
        "rfk_id": "ph_professional-list", "total_item": total,
        "offset": offset, "limit": limit, "content": list(rows),
    }]}})


class PaulHastingsTests(unittest.TestCase):
    def setUp(self):
        self.config = load_firms()["paul_hastings"]
        self.session = Mock()
        self.connector = PaulHastingsConnector(
            "paul_hastings",
            {**self.config, "page_size": 2, "request_interval_seconds": 0},
            self.session,
        )

    def test_paginates_and_merges_practices_including_leadership_titles(self):
        self.session.post.side_effect = [
            page(3, 0, 2, row("alex", MA, "Global Managing Partner"), row("blake", MA)),
            page(3, 2, 1, row("casey", MA)),
            page(2, 0, 2, row("blake", CAPITAL_MARKETS), row("drew", CAPITAL_MARKETS, "Chair of the Firm")),
        ]
        result = self.connector.extract()
        searches = [call.kwargs["json"]["widget"]["items"][0]["search"] for call in self.session.post.call_args_list]
        self.assertEqual([search["offset"] for search in searches], [0, 2, 0])
        facets = searches[-1]["facet"]["types"]
        self.assertEqual(
            [(facet["name"], facet["filter"]["values"][0]["value"]) for facet in facets],
            [("ph_professional_position", "Partner"), ("ph_nested_practice_areas", CAPITAL_MARKETS)],
        )
        self.assertEqual(result.expected_total, 4)
        self.assertTrue(result.extraction_complete)
        self.assertFalse(result.scope_verified)
        self.assertEqual(result.records[0].role, "Global Managing Partner")
        self.assertEqual(result.records[1].practices, [MA, CAPITAL_MARKETS])
        self.assertEqual(result.records[-1].role, "Chair of the Firm")
        profiles = Mock()
        enrichment = enrich_entries(result.records, profiles, directory_summaries={
            ("paul_hastings", url): summary for url, summary in result.directory_summaries.items()
        })
        self.assertEqual(len(enrichment.profiles), 4)
        self.assertEqual(enrichment.profiles[0].biography, "Advises on transactions.")
        profiles.enrich.assert_not_called()

    def test_rejects_duplicate_profiles_within_a_search(self):
        self.session.post.side_effect = [
            page(3, 0, 2, row("alex", MA), row("blake", MA)),
            page(3, 2, 1, row("alex", MA)),
        ]
        with self.assertRaisesRegex(UnexpectedResponseError, "repeated a profile"):
            self.connector.extract()

    def test_rejects_incomplete_page(self):
        self.session.post.return_value = page(3, 0, 2, row("alex", MA))
        with self.assertRaisesRegex(UnexpectedResponseError, "inconsistent results"):
            self.connector.extract()

    def test_rejects_out_of_scope_profile(self):
        self.session.post.return_value = page(1, 0, 1, row("alex", CAPITAL_MARKETS))
        with self.assertRaisesRegex(UnexpectedResponseError, "unconfirmed partner"):
            self.connector.extract()

    def test_registered_for_partial_publication(self):
        self.assertIsInstance(build_connector("paul_hastings", self.config), PaulHastingsConnector)
        self.assertTrue(self.config["refresh_enabled"])
        self.assertTrue(self.config["publish_partial_scope"])
