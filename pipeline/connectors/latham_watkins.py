"""Collect the documented subset of Latham's public People directory."""

import re
from time import sleep
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup

from pipeline.connectors.base import Connector
from pipeline.connectors.errors import ConnectorError, UnexpectedResponseError
from pipeline.connectors.http import DEFAULT_TIMEOUT_SECONDS, build_session
from pipeline.models import ExtractionResult, PartnerEntryInfo
from pipeline.processing.deduplicate import deduplicate_records


class LathamWatkinsConnector(Connector):
    def __init__(self, firm_key, config, session=None):
        super().__init__(firm_key, config)
        self.session = session or build_session()

    def extract(self) -> ExtractionResult:
        headers = self._search_headers()
        records = []
        pages_fetched = 0
        practices = self.config["practice_filters"]
        for practice in practices:
            offset = 0
            total = None
            profiles = set()
            while total is None or offset < total:
                if pages_fetched:
                    sleep(self.config["request_interval_seconds"])
                payload = self._fetch(practice, offset, headers)
                reported = payload.get("totalCount")
                rows = payload.get("results")
                if (
                    type(reported) is not int or reported <= 0
                    or (total is not None and reported != total)
                    or payload.get("totalCountFiltered") != reported
                    or not isinstance(rows, list)
                    or len(rows) != min(self.config["page_size"], reported - offset)
                ):
                    raise UnexpectedResponseError(f"Latham {practice} returned inconsistent results at offset {offset}")
                total = reported
                for row in rows:
                    entry = self._parse_row(row, practice)
                    if entry.profile_url in profiles:
                        raise UnexpectedResponseError(f"Latham {practice} returned a duplicate profile at offset {offset}")
                    profiles.add(entry.profile_url)
                    records.append(entry)
                offset += len(rows)
                pages_fetched += 1

        unique = deduplicate_records(records)
        return ExtractionResult(
            firm_key=self.firm_key,
            records=unique,
            expected_total=len(unique),
            pages_fetched=pages_fetched,
            extraction_complete=True,
            scope_verified=False,
            covered_practices=list(practices),
            missing_practices=["Other Corporate practice groups"],
        )

    def _search_headers(self):
        directory = self.config["directory_url"]
        try:
            response = self.session.get(directory, timeout=DEFAULT_TIMEOUT_SECONDS)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ConnectorError(f"Latham People page request failed: {exc}") from exc
        soup = BeautifulSoup(response.content, "html.parser")
        for script in soup.find_all("script"):
            source = script.string or ""
            if "searchInterface.initialize" in source:
                token = re.search(r"""const\s+accessToken\s*=\s*["']([^"']+)["']""", source)
                if token:
                    origin = urlsplit(directory)
                    return {
                        "Authorization": f"Bearer {token[1]}",
                        "Origin": f"{origin.scheme}://{origin.netloc}",
                    }
        raise UnexpectedResponseError("Latham People page did not expose its public search configuration")

    def _fetch(self, practice, offset, headers):
        body = {
            "locale": "en",
            "searchHub": "default",
            "q": "",
            "aq": (
                '(@z95xlanguage=="en") AND (@peoplebuckettitle=="Partner") '
                f'AND (@peoplepractices=="{practice}")'
            ),
            "firstResult": offset,
            "numberOfResults": self.config["page_size"],
            "sortCriteria": "@peoplerankbytitle ascending,@peoplelastname ascending",
            "fieldsToInclude": [
                "peoplepractices", "peoplebuckettitle", "peopleformattedname",
                "peopleemployeetitle", "peopleoffices",
            ],
        }
        try:
            response = self.session.post(
                self.config["results_url"],
                params={"organizationId": self.config["organization_id"]},
                headers=headers, json=body, timeout=DEFAULT_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise ConnectorError(f"Latham {practice} search failed at offset {offset}: {exc}") from exc
        if not isinstance(payload, dict):
            raise UnexpectedResponseError(f"Latham {practice} returned malformed search results")
        return payload

    def _parse_row(self, row, practice):
        raw = row.get("raw") if isinstance(row, dict) else None
        if not isinstance(raw, dict):
            raise UnexpectedResponseError(f"Latham {practice} returned a malformed profile")
        name = raw.get("peopleformattedname")
        url = row.get("clickUri")
        roles = self._values(raw.get("peoplebuckettitle"))
        practices = self._values(raw.get("peoplepractices"))
        if (
            not isinstance(name, str) or not name.strip() or not isinstance(url, str)
            or "Partner" not in roles or practice not in practices
        ):
            raise UnexpectedResponseError(f"Latham {practice} returned an unconfirmed partner profile")
        profile = urlsplit(url)
        path = profile.path.rstrip("/")
        if (
            profile.scheme != "https"
            or profile.netloc != urlsplit(self.config["directory_url"]).netloc
            or not re.fullmatch(r"/en/people/[^/]+", path)
        ):
            raise UnexpectedResponseError(f"Latham {practice} returned an invalid profile URL")
        return PartnerEntryInfo(
            firm_key=self.firm_key, firm_name=self.config["name"], name=name.strip(),
            role="Partner", offices=self._values(raw.get("peopleoffices")), practices=practices,
            profile_url=profile._replace(path=path, query="", fragment="").geturl(),
            source_url=self.config["directory_url"],
        )

    @staticmethod
    def _values(value):
        if isinstance(value, str):
            return [value]
        return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []
