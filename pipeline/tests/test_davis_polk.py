import unittest
from unittest.mock import Mock

from pipeline.connectors.davis_polk import DavisPolkConnector


class DavisPolkTests(unittest.TestCase):
    def test_keeps_supported_partner_title_and_excludes_counsel(self):
        source = "https://www.davispolk.com/example/team"
        cards = ""
        for slug, role in (
            ("ordinary", "Partner"), ("lead", "Head of Practice"),
            ("counsel", "Counsel"), ("special-counsel", "Special Counsel"),
        ):
            cards += f"""
              <article class="lawyer--teaser">
                <a class="lawyer-teaser-link" href="/lawyers/{slug}"></a>
                <div class="lawyer--name">{slug}</div>
                <div class="field-name--field_job_title_custom">{role}</div>
              </article>
            """
        page = f"""
          <div class="view-lawyers-by-practice">
            <select name="field_job_title_category_value">
              <option value="Partner" selected>Partner</option>
            </select>
            <select name="field_lawyer_offices_target_id">
              <option value="All" selected>All offices</option>
            </select>
            {cards}
          </div>
        """
        session = Mock()
        session.get.return_value = Mock(content=page, url=source)
        connector = DavisPolkConnector(
            "davis_polk",
            {"name": "Example firm", "verified_partner_titles": {"/lawyers/lead": "Head of Practice"}},
            session,
        )
        records, pages = connector._extract_team(source, "Example practice")
        self.assertEqual(pages, 1)
        self.assertEqual([(entry.name, entry.role) for entry in records], [
            ("ordinary", "Partner"), ("lead", "Head of Practice"),
        ])

    def test_empty_partner_filter_requires_complete_nonpartner_team(self):
        team = """
          <div class="view-lawyers-by-practice">
            <select name="field_job_title_category_value">
              <option value="All">All</option>
              <option value="Counsel">Counsel</option>
            </select>
            <article class="lawyer--teaser">
              <div class="field-name--field_job_title">Counsel</div>
            </article>
          </div>
        """
        for case, original in (
            ("verified empty", team),
            ("advertises partner filter", team.replace('value="Counsel"', 'value="Partner"')),
            ("additional pages", team.replace("</article>", '</article><div class="pager"><a href="?page=1">Next</a></div>')),
            ("contains partner", team.replace('>Counsel</div>', '>Partner</div>')),
        ):
            with self.subTest(case=case):
                response = Mock(content=original)
                session = Mock()
                session.get.return_value = response
                connector = DavisPolkConnector("davis_polk", {}, session)
                self.assertEqual(
                    connector._verify_no_partners("https://www.davispolk.com/example/team"),
                    case == "verified empty",
                )
