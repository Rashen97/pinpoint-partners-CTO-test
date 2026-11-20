import unittest
from unittest.mock import Mock

from pipeline.config import load_firms
from pipeline.connectors import build_connector
from pipeline.connectors.errors import UnexpectedResponseError
from pipeline.connectors.weil import PRACTICE_PARAM, WeilConnector
from pipeline.models import PartnerEntryInfo
from pipeline.profile_enrichment.config import load_profile_sources
from pipeline.profile_enrichment.connector import ConfiguredHtmlProfileConnector


def card(slug, title="Partner"):
    return f"""
        <h3><a href="/people/{slug}">{slug}</a></h3>
        <p class="ppl-item-status"><b>{title}</b><a href="/locations/london">London</a></p>
        <p class="ppl-item-categories"><a href="/experience/practices/ma">M&A</a></p>
    """


def page(number, *groups):
    return Mock(url="https://www.weil.com/WeilPeopleListing/Execute", **{
        "json.return_value": {
            "TotalCount": 3, "PageNumber": number, "TotalPages": 2, "PageSize": 2,
            "SearchGroups": [
                {"Title": title, "SearchResultItemsAsHtml": cards} for title, cards in groups
            ],
        },
    })


class WeilTests(unittest.TestCase):
    def setUp(self):
        self.session = Mock()
        self.config = load_firms()["weil"]
        self.connector = WeilConnector("weil", {
            **self.config,
            "page_size": 2,
            "request_interval_seconds": 0,
            "practice_filters": {"Mergers & Acquisitions": "practice-id"},
        }, self.session)

    def test_registered_for_expected_partial_publication(self):
        self.assertIsInstance(build_connector("weil", self.config), WeilConnector)
        self.assertTrue(self.config["refresh_enabled"])
        self.assertTrue(self.config["publish_partial_scope"])
        self.assertTrue(self.config["expected_partial_scope"])

    def test_enriches_profile_and_rejects_identity_mismatch(self):
        connector = ConfiguredHtmlProfileConnector(load_profile_sources(), self.session)
        entry = PartnerEntryInfo(
            firm_key="weil", name="Alex Morgan", role="Partner", offices=["London"],
            practices=["M&A"], profile_url="https://www.weil.com/people/alex",
            source_url=self.config["directory_url"],
        )
        html = """
            <header class="header-b"><h1>Alex Morgan</h1></header>
            <div class="bio-top"><div class="intro"><p>Advises on acquisitions.</p></div></div>
        """
        self.assertEqual(connector.parse(entry, html).biography, "Advises on acquisitions.")
        with self.assertRaisesRegex(UnexpectedResponseError, "does not match directory name"):
            connector.parse(entry, html.replace("Alex Morgan", "Casey Morgan"))

    def test_reconciles_duplicate_leadership_and_excludes_unverified_title(self):
        self.session.get.side_effect = [
            page(1, ("Leadership", [card("leader")]),
                 ("A", [card("alex"), card("counsel", "General Counsel")])),
            page(2, ("L", [card("leader")])),
        ]

        result = self.connector.extract()

        self.assertEqual(result.pages_fetched, 2)
        self.assertTrue(result.extraction_complete)
        self.assertFalse(result.scope_verified)
        self.assertEqual([entry.name for entry in result.records], ["leader", "alex"])
        self.assertEqual(result.records[0].offices, ["London"])
        self.assertEqual(result.records[0].practices, ["Mergers & Acquisitions", "M&A"])
        self.assertIn("Excluded 1 profiles", result.warnings[-1])
        params = [call.kwargs["params"] for call in self.session.get.call_args_list]
        self.assertEqual([param["pagenum"] for param in params], [1, 2])
        self.assertTrue(all(param[PRACTICE_PARAM] == "practice-id" for param in params))
        self.assertTrue(all(param["param_role_s"] == self.config["partner_role_id"] for param in params))

    def test_rejects_wrong_page_number(self):
        self.session.get.side_effect = [
            page(1, ("A", [card("alex"), card("anna")])),
            page(1, ("B", [card("blake")])),
        ]

        with self.assertRaisesRegex(UnexpectedResponseError, "pagination disagreed on page 2"):
            self.connector.extract()

    def test_rejects_short_unique_count(self):
        self.session.get.side_effect = [
            page(1, ("A", [card("alex"), card("anna")])),
            page(2, ("A", [card("alex")])),
        ]

        with self.assertRaisesRegex(UnexpectedResponseError, "reported 3 results but returned 2"):
            self.connector.extract()
