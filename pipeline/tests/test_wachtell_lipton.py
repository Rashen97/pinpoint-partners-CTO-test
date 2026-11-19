from __future__ import annotations

import unittest

from pipeline.connectors.errors import UnexpectedResponseError
from pipeline.connectors.wachtell_lipton import WachtellLiptonConnector


CONFIG = {
    "name": "Wachtell, Lipton, Rosen & Katz",
    "directory_url": "https://www.wlrk.com/attorneys/",
    "results_url": "https://www.wlrk.com/attorneys/",
    "query_params": {"asf_pa": "corporate"},
}

HTML = """
<select name="asf_pa"><option value="corporate" selected>Corporate</option></select>
<div class="attorneys-search--results">
  <ul>
    <li class="attorneys-search--results-item attorneys-search--results-item-header">Position</li>
    <li class="attorneys-search--results-item">
      <a href="/attorney/alex-example/">
        <span class="attorneys-search--results-item-name">Alex Example</span>
        <span class="attorneys-search--results-item-position">Partner</span>
      </a>
    </li>
    <li class="attorneys-search--results-item">
      <a href="/attorney/alex-example">
        <span class="attorneys-search--results-item-name">Alex Example</span>
        <span class="attorneys-search--results-item-position">Partner</span>
      </a>
    </li>
    <li class="attorneys-search--results-item">
      <a href="/attorney/blair-example/">
        <span class="attorneys-search--results-item-name">Blair Example</span>
        <span class="attorneys-search--results-item-position">Associate</span>
      </a>
    </li>
  </ul>
</div>
"""


class WachtellLiptonTests(unittest.TestCase):
    def test_parses_and_deduplicates_profile_links(self) -> None:
        connector = WachtellLiptonConnector("wachtell_lipton", CONFIG)
        records = connector._parse(HTML, CONFIG["results_url"])

        self.assertEqual([record.name for record in records], ["Alex Example"])
        self.assertEqual(records[0].role, "Partner")
        self.assertEqual(records[0].practices, ["Corporate"])

    def test_rejects_unconfirmed_filter(self) -> None:
        connector = WachtellLiptonConnector("wachtell_lipton", CONFIG)
        with self.assertRaisesRegex(UnexpectedResponseError, "asf_pa=corporate"):
            connector._parse(
                HTML.replace(' selected>Corporate', '>Corporate'),
                CONFIG["results_url"],
            )


if __name__ == "__main__":
    unittest.main()
