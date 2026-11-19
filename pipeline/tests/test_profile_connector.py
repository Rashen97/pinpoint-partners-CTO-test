from __future__ import annotations

import unittest

from pipeline.connectors.errors import UnexpectedResponseError
from pipeline.models import PartnerEntryInfo
from pipeline.profile_enrichment.connector import ConfiguredHtmlProfileConnector


SOURCES = {
    "example_firm": {
        "selectors": {
            "name": "h1",
            "role": ".role",
            "biography": ".biography",
            "offices": ".office",
            "practices": ".practice",
            "phone_numbers": {
                "selector": "a[href^='tel:']",
                "attribute": "href",
                "strip_prefix": "tel:",
            },
            "education": ".education li",
        }
    }
}

HTML = """
<h1>Alex Example</h1>
<p class="role">Partner</p>
<div class="biography">Alex advises clients on transactions.</div>
<span class="office">London</span>
<span class="practice">Mergers &amp; Acquisitions</span>
<a href="tel:+44-20-1234-5678">Call</a>
<ul class="education"><li>Example University</li></ul>
"""


def entry() -> PartnerEntryInfo:
    return PartnerEntryInfo(
        firm_key="example_firm",
        firm_name="Example Firm",
        name="Alex Example",
        role="Partner",
        offices=["London"],
        practices=["Corporate"],
        profile_url="https://example.com/alex",
        source_url="https://example.com/directory",
        partner_entry_id="entry-123",
    )


class ConfiguredProfileConnectorTests(unittest.TestCase):
    def test_parses_and_merges_profile_with_directory_values(self) -> None:
        connector = ConfiguredHtmlProfileConnector(SOURCES)

        profile = connector.parse(entry(), HTML)

        self.assertEqual(profile.name, "Alex Example")
        self.assertEqual(profile.offices, ["London"])
        self.assertEqual(
            profile.practices,
            ["Corporate", "Mergers & Acquisitions"],
        )
        self.assertEqual(profile.phone_numbers, ["+44-20-1234-5678"])
        self.assertEqual(profile.education, ["Example University"])
        self.assertEqual(profile.partner_entry_id, "entry-123")
        self.assertEqual(len(profile.content_hash), 64)

    def test_rejects_a_profile_for_a_different_person(self) -> None:
        connector = ConfiguredHtmlProfileConnector(SOURCES)

        with self.assertRaisesRegex(UnexpectedResponseError, "does not match"):
            connector.parse(entry(), HTML.replace("Alex Example", "Blair Other"))

    def test_hash_changes_when_education_changes(self) -> None:
        connector = ConfiguredHtmlProfileConnector(SOURCES)
        original = connector.parse(entry(), HTML)
        changed = connector.parse(entry(), HTML.replace("Example University", "Other University"))

        self.assertNotEqual(original.content_hash, changed.content_hash)


if __name__ == "__main__":
    unittest.main()
