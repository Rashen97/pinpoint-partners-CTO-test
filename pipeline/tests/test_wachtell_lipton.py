from __future__ import annotations

import unittest

from pipeline.connectors.errors import UnexpectedResponseError
from pipeline.connectors.wachtell_lipton import WachtellLiptonConnector


CONFIG = {
    "name": "Wachtell, Lipton, Rosen & Katz",
    "directory_url": "https://www.wlrk.com/attorneys/",
    "results_url": "https://www.wlrk.com/attorneys/",
    "query_params": {"asf_pa": "corporate", "asf_p": "partner"},
}

HTML = """
<select name="asf_pa"><option value="corporate" selected>Corporate</option></select>
<select name="asf_p"><option value="partner" selected>Partner</option></select>
<a href="/attorney/alex-example/"><img alt="Alex Example"></a>
<a href="/attorney/alex-example/">Alex Example</a>
<a href="/attorney/blair-example/">Blair Example</a>
"""


class WachtellLiptonTests(unittest.TestCase):
    def test_parses_and_deduplicates_profile_links(self) -> None:
        connector = WachtellLiptonConnector("wachtell_lipton", CONFIG)
        records = connector._parse(HTML, CONFIG["results_url"])

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].practices, ["Corporate"])

    def test_rejects_unconfirmed_filter(self) -> None:
        connector = WachtellLiptonConnector("wachtell_lipton", CONFIG)
        with self.assertRaisesRegex(UnexpectedResponseError, "asf_p=partner"):
            connector._parse(
                HTML.replace(' selected>Partner', '>Partner'),
                CONFIG["results_url"],
            )


if __name__ == "__main__":
    unittest.main()
