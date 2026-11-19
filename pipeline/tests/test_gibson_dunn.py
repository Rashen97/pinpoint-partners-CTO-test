import unittest
from unittest.mock import Mock

from pipeline.connectors.gibson_dunn import GibsonDunnConnector


class GibsonDunnTests(unittest.TestCase):
    def test_merges_verified_filters_without_claiming_full_corporate_scope(self):
        def response(url, *, params, **kwargs):
            slug = params["_people_practices"]
            return Mock(**{"json.return_value": {
                "total": 2,
                "facets": {
                    "practice": {"slug": "people_practices", "selected": [slug]},
                    "title": {"slug": "people_title", "selected": ["000_partner"]},
                },
                "posts": """
                    <div class="people">
                      <a href="/lawyer/example/"><p class="name">Example Partner</p></a>
                      <p class="title"><span>Partner</span></p>
                    </div>
                    <div class="people">
                      <a href="/lawyer/counsel/"><p class="name">Example Counsel</p></a>
                      <p class="title"><span>Counsel</span></p>
                    </div>
                """,
            }})

        directory = "https://www.gibsondunn.com/people/"
        session = Mock()
        session.get.return_value = Mock(content='<div class="wpgb-facet" data-grid="archivePeople" data-facet="42"></div>')
        session.post.side_effect = response
        connector = GibsonDunnConnector("gibson_dunn", {
            "name": "Gibson Dunn",
            "directory_url": directory,
            "filtered_url": directory,
            "results_url": "https://www.gibsondunn.com/?wpgb-ajax=refresh",
            "practice_filters": [
                {"label": "M&A", "slug": "mergers-and-acquisitions"},
                {"label": "Capital Markets", "slug": "capital-markets"},
            ],
        }, session)

        result = connector.extract()

        self.assertEqual(result.pages_fetched, 2)
        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.records[0].practices, ["M&A", "Capital Markets"])
        self.assertTrue(result.extraction_complete)
        self.assertFalse(result.scope_verified)
