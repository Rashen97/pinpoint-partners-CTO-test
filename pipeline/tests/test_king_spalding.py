import unittest
from unittest.mock import Mock

from pipeline.config import load_firms
from pipeline.connectors import build_connector
from pipeline.connectors.errors import UnexpectedResponseError
from pipeline.connectors.king_spalding import KingSpaldingConnector
from pipeline.profile_enrichment.config import load_profile_sources
from pipeline.profile_enrichment.connector import ConfiguredHtmlProfileConnector


MA = "Mergers & Acquisitions (M&A)"
CAPITAL_MARKETS = "Capital Markets"


def hit(slug, title="Partner"):
    return {
        "url": f"/people/{slug}", "category": "people",
        "metadata": {
            "PersonName": slug, "BusinessTitle": title,
            "OfficesJson": '[{"Name":"London"},{"Name":"New York"}]',
        },
    }


def page(number, total, total_pages, *hits):
    return Mock(**{"json.return_value": {
        "page": number, "pageSize": 2, "totalHits": total,
        "totalPages": total_pages, "hits": list(hits),
    }})


class KingSpaldingTests(unittest.TestCase):
    def setUp(self):
        self.config = load_firms()["king_spalding"]
        self.session = Mock()
        self.connector = KingSpaldingConnector("king_spalding", {
            **self.config, "page_size": 2, "request_interval_seconds": 0,
            "capability_filters": [MA, CAPITAL_MARKETS],
        }, self.session)

    def test_paginates_and_merges_overlapping_capabilities(self):
        self.session.post.side_effect = [
            page(1, 3, 2, hit("alex", "Managing Partner Atlanta Office"), hit("blake")),
            page(2, 3, 2, hit("casey")),
            page(1, 1, 1, hit("blake")),
        ]
        result = self.connector.extract()
        bodies = [call.kwargs["json"] for call in self.session.post.call_args_list]
        self.assertEqual([body["Page"] for body in bodies], [1, 2, 1])
        self.assertEqual(bodies[-1]["SelectedFilters"]["Capability"], [CAPITAL_MARKETS])
        self.assertEqual(result.expected_total, 3)
        self.assertTrue(result.extraction_complete)
        self.assertFalse(result.scope_verified)
        self.assertEqual(result.records[0].role, "Managing Partner Atlanta Office")
        self.assertEqual(result.records[0].offices, ["London", "New York"])
        self.assertEqual(result.records[1].practices, [MA, CAPITAL_MARKETS])

        profile = ConfiguredHtmlProfileConnector(load_profile_sources()).parse(result.records[0], """
            <main class="kslaw-bio">
              <section class="bio-page-hero screen-only"><h1 class="bio-page-hero__header">alex</h1></section>
              <div class="expandable-copy-block__copy"><ul><li>Prior transaction</li></ul></div>
              <div class="expandable-copy-block__copy"><p>Advises on acquisitions.</p></div>
            </main>
        """)
        self.assertEqual(profile.biography, "Advises on acquisitions.")

    def test_rejects_repeated_profile(self):
        self.session.post.side_effect = [
            page(1, 3, 2, hit("alex"), hit("blake")),
            page(2, 3, 2, hit("alex")),
        ]
        with self.assertRaisesRegex(UnexpectedResponseError, "repeated a profile"):
            self.connector.extract()

    def test_rejects_inconsistent_page(self):
        self.session.post.return_value = page(1, 3, 2, hit("alex"))
        with self.assertRaisesRegex(UnexpectedResponseError, "inconsistent results"):
            self.connector.extract()

    def test_rejects_unconfirmed_title(self):
        self.session.post.return_value = page(1, 1, 1, hit("alex", "Counsel"))
        with self.assertRaisesRegex(UnexpectedResponseError, "unconfirmed partner"):
            self.connector.extract()

    def test_registered_for_expected_partial_publication(self):
        self.assertIsInstance(build_connector("king_spalding", self.config), KingSpaldingConnector)
        self.assertTrue(self.config["refresh_enabled"])
        self.assertTrue(self.config["publish_partial_scope"])
        self.assertTrue(self.config["expected_partial_scope"])
