"""Read Paul Hastings' public Sitecore Discover professionals widget."""

import re
from time import sleep
from urllib.parse import urlsplit

import requests

from pipeline.connectors.base import Connector
from pipeline.connectors.errors import ConnectorError, UnexpectedResponseError
from pipeline.connectors.http import DEFAULT_TIMEOUT_SECONDS, build_session
from pipeline.models import ExtractionResult, PartnerEntryInfo
from pipeline.processing.deduplicate import deduplicate_records


WIDGET_ID = "ph_professional-list"


class PaulHastingsConnector(Connector):
    def __init__(self, firm_key, config, session=None):
        super().__init__(firm_key, config)
        self.session = session or build_session()

    def extract(self) -> ExtractionResult:
        records = []
        pages = 0
        practices = self.config["practice_filters"]
        page_size = self.config["page_size"]
        for practice in practices:
            profiles = set()
            total = None
            offset = 0
            while total is None or offset < total:
                if pages:
                    sleep(self.config["request_interval_seconds"])
                widget = self._fetch(practice, offset)
                reported = widget.get("total_item")
                rows = widget.get("content")
                if (
                    type(reported) is not int or reported <= offset
                    or (total is not None and reported != total)
                    or widget.get("offset") != offset
                    or not isinstance(rows, list)
                    or len(rows) != min(page_size, reported - offset)
                ):
                    raise UnexpectedResponseError(f"Paul Hastings {practice} returned inconsistent results at offset {offset}")
                total = reported
                for row in rows:
                    entry = self._parse_row(row, practice)
                    if entry.profile_url in profiles:
                        raise UnexpectedResponseError(f"Paul Hastings {practice} repeated a profile at offset {offset}")
                    profiles.add(entry.profile_url)
                    records.append(entry)
                offset += len(rows)
                pages += 1

        unique = deduplicate_records(records)
        return ExtractionResult(
            firm_key=self.firm_key,
            records=unique,
            expected_total=len(unique),
            pages_fetched=pages,
            extraction_complete=True,
            scope_verified=False,
            covered_practices=list(practices),
            missing_practices=["Broader Corporate practice scope"],
        )

    def _fetch(self, practice, offset):
        filters = [
            {"name": name, "filter": {"type": "or", "values": [{"type": "eq", "value": value}]}}
            for name, value in (
                ("ph_professional_position", "Partner"),
                ("ph_nested_practice_areas", practice),
            )
        ]
        body = {
            "context": {
                "page": {"uri": "/professionals", "custom": {"environment": "prod"}},
                "locale": {"country": "us", "language": "en"},
            },
            "widget": {"items": [{
                "rfk_id": WIDGET_ID,
                "entity": "content",
                "search": {
                    "content": {}, "facet": {"all": True, "types": filters},
                    "offset": offset, "limit": self.config["page_size"],
                    "sort": {"choices": True},
                    "query": {"highlight": {"fragment_size": 500, "fields": ["ph_teaser", "description"]}, "operator": "and"},
                },
            }]},
        }
        try:
            response = self.session.post(
                self.config["results_url"], json=body, timeout=DEFAULT_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            widgets = response.json()["widgets"]
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            raise ConnectorError(f"Paul Hastings {practice} search failed at offset {offset}: {exc}") from exc
        if (
            not isinstance(widgets, list) or len(widgets) != 1
            or not isinstance(widgets[0], dict) or widgets[0].get("rfk_id") != WIDGET_ID
        ):
            raise UnexpectedResponseError(f"Paul Hastings {practice} did not return the professionals widget")
        return widgets[0]

    def _parse_row(self, row, practice):
        if not isinstance(row, dict):
            raise UnexpectedResponseError(f"Paul Hastings {practice} returned a malformed profile")
        name = row.get("ph_navigation_title")
        title = row.get("ph_professional_title_position")
        url = row.get("url")
        practices = row.get("ph_nested_practice_areas")
        if (
            row.get("ph_content_type") != "Professional"
            or not isinstance(name, str) or not name.strip() or not isinstance(url, str)
            or not isinstance(practices, list) or practice not in practices
            or not isinstance(title, str) or not (
                re.match(r"^(?:Partner\b|Global Managing Partner\b)", title)
                or title == "Chair of the Firm"
            )
        ):
            raise UnexpectedResponseError(f"Paul Hastings {practice} returned an unconfirmed partner profile")
        profile = urlsplit(url)
        path = profile.path.rstrip("/")
        directory = self.config["directory_url"]
        if (
            profile.scheme != "https" or profile.netloc != urlsplit(directory).netloc
            or not re.fullmatch(r"/professionals/[^/]+", path)
        ):
            raise UnexpectedResponseError(f"Paul Hastings {practice} returned an invalid profile URL")
        offices = row.get("ph_nested_offices") or []
        if not isinstance(offices, list) or any(not isinstance(office, str) for office in offices):
            raise UnexpectedResponseError(f"Paul Hastings {practice} returned malformed offices")
        return PartnerEntryInfo(
            firm_key=self.firm_key, firm_name=self.config["name"], name=name.strip(),
            role=title, offices=offices, practices=practices,
            profile_url=profile._replace(path=path, query="", fragment="").geturl(),
            source_url=directory,
        )
