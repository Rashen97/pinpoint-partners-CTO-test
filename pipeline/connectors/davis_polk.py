"""Read the public practice teams Davis Polk lists under Corporate."""

import re
from time import sleep
from urllib.parse import urlencode, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from pipeline.connectors.base import Connector
from pipeline.connectors.errors import ConnectorError, UnexpectedResponseError
from pipeline.connectors.http import DEFAULT_TIMEOUT_SECONDS, build_session
from pipeline.models import ExtractionResult, PartnerEntryInfo
from pipeline.processing.deduplicate import deduplicate_records


class DavisPolkConnector(Connector):
    def __init__(self, firm_key, config, session=None):
        super().__init__(firm_key, config)
        self.session = session or build_session()

    def extract(self) -> ExtractionResult:
        ma_label = "Mergers & Acquisitions"
        ma_source = self.config["practice_team_url"]
        records, pages = self._extract_team(ma_source, ma_label)
        covered = [ma_label]
        missing = []
        warnings = []
        try:
            teams = self._corporate_teams()
        except ConnectorError as exc:
            teams = {}
            missing.append("Corporate")
            warnings.append(str(exc))

        for practice, source in teams.items():
            if source == ma_source:
                continue
            try:
                batch, pages_fetched = self._extract_team(source, practice)
            except UnexpectedResponseError as exc:
                missing.append(practice)
                warnings.append(f"{practice}: {exc}")
                continue
            except ConnectorError as exc:
                missing.extend(label for label in teams if label not in covered and label not in missing)
                warnings.append(f"{practice}: {exc}")
                break
            records.extend(batch)
            pages += pages_fetched
            covered.append(practice)

        return ExtractionResult(
            firm_key=self.firm_key,
            records=deduplicate_records(records),
            pages_fetched=pages,
            extraction_complete=True,
            scope_verified=not missing,
            covered_practices=covered,
            missing_practices=missing,
            warnings=warnings,
        )

    def _corporate_teams(self) -> dict[str, str]:
        source = self.config["corporate_overview_url"]
        response = self._get(source)
        soup = BeautifulSoup(response.content, "html.parser")
        heading = next(
            (node for node in soup.select("h2, h3")
             if node.get_text(" ", strip=True) == "Corporate practices"),
            None,
        )
        teams = {}
        if heading is not None:
            for link in heading.parent.select("a[href]"):
                label = link.get_text(" ", strip=True)
                url = urlsplit(urljoin(source, link["href"]))
                if label and url.netloc == urlsplit(source).netloc and url.scheme == "https":
                    teams[label] = url._replace(
                        path=url.path.rstrip("/") + "/team", query="", fragment=""
                    ).geturl()
        minimum = self.config["minimum_corporate_practices"]
        if self.config["practice_team_url"] not in teams.values() or len(teams) < minimum:
            raise UnexpectedResponseError("Davis Polk Corporate practice list could not be verified")
        return teams

    def _get(self, url):
        sleep(self.config.get("request_interval_seconds", 0))
        try:
            response = self.session.get(url, timeout=DEFAULT_TIMEOUT_SECONDS)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            raise ConnectorError(f"Davis Polk request failed: {exc}") from exc

    def _extract_team(self, source: str, practice: str) -> tuple[list[PartnerEntryInfo], int]:
        team_url = urlsplit(source)
        host = team_url.netloc
        seen_pages = set()
        seen_profiles = set()
        records = []
        url = source + "?" + urlencode({
            "sub-page": "team",
            "field_job_title_category_value": "Partner",
            "field_lawyer_offices_target_id": "All",
        })
        while url:
            page_url = urlsplit(url)
            if (
                url in seen_pages or page_url.scheme != "https" or page_url.netloc != host
                or page_url.path.rstrip("/") != team_url.path.rstrip("/")
            ):
                raise UnexpectedResponseError("Davis Polk pager repeated a page or left the practice team")
            seen_pages.add(url)
            response = self._get(url)
            soup = BeautifulSoup(response.content, "html.parser")
            team = soup.select_one(".view-lawyers-by-practice")
            cards = team.select("article.lawyer--teaser") if team else []
            if not cards:
                if len(seen_pages) == 1 and self._verify_no_partners(source):
                    return [], 2
                raise UnexpectedResponseError("Davis Polk practice team returned no attorney cards")
            if not team.select_one('[name="field_job_title_category_value"] [value="Partner"][selected]'):
                raise UnexpectedResponseError("Davis Polk practice team did not confirm the Partner filter")
            if not team.select_one('[name="field_lawyer_offices_target_id"] [value="All"][selected]'):
                raise UnexpectedResponseError("Davis Polk practice team did not confirm all offices")
            for card in cards:
                link = card.select_one("a.lawyer-teaser-link[href]")
                title = card.select_one(".field-name--field_job_title_custom, .field-name--field_job_title")
                name = card.select_one(".lawyer--name")
                if link is None or title is None or name is None:
                    raise UnexpectedResponseError("Davis Polk attorney card is missing key fields")
                role = title.get_text(" ", strip=True)
                profile = urlsplit(urljoin(response.url, link["href"]))
                if profile.netloc != host or not profile.path.startswith("/lawyers/"):
                    raise UnexpectedResponseError("Davis Polk attorney card has an invalid profile URL")
                profile_url = f"https://{host}{profile.path.rstrip('/')}"
                if profile_url in seen_profiles:
                    raise UnexpectedResponseError("Davis Polk returned a duplicate profile across pages")
                seen_profiles.add(profile_url)
                if role in {"Counsel", "Special Counsel"}:
                    continue
                supported_title = self.config.get("verified_partner_titles", {}).get(profile.path.rstrip("/"))
                if not re.search(r"\bPartner\b", role) and role != supported_title:
                    raise UnexpectedResponseError(f"Davis Polk returned an unverified Partner title: {role!r}")
                records.append(PartnerEntryInfo(
                    firm_key=self.firm_key,
                    firm_name=self.config["name"],
                    name=name.get_text(" ", strip=True),
                    role=role,
                    offices=[node.get_text(" ", strip=True) for node in card.select(".field-name--field_lawyer_offices .field-item")],
                    practices=[practice],
                    profile_url=profile_url,
                    source_url=source,
                ))
            next_page = team.select_one(".pager a[href]")
            url = urljoin(response.url, next_page["href"]) if next_page else ""

        return records, len(seen_pages)

    def _verify_no_partners(self, source: str) -> bool:
        response = self._get(source)
        soup = BeautifulSoup(response.content, "html.parser")
        team = soup.select_one(".view-lawyers-by-practice")
        if team is None or team.select_one(".pager a[href]"):
            return False
        title_filter = team.select_one('[name="field_job_title_category_value"]')
        cards = team.select("article.lawyer--teaser")
        if title_filter is None or title_filter.select_one('[value="Partner"]') or not cards:
            return False
        for card in cards:
            title = card.select_one(".field-name--field_job_title_custom, .field-name--field_job_title")
            if title is None or not re.fullmatch(
                r"(?:Counsel|Associate)(?:\s*[-–].+)?", title.get_text(" ", strip=True)
            ):
                return False
        return True
