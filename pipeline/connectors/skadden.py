"""Read Skadden's public Professionals search."""

import re
from time import sleep
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from pipeline.connectors.base import Connector
from pipeline.connectors.errors import ConnectorError, UnexpectedResponseError
from pipeline.connectors.http import DEFAULT_TIMEOUT_SECONDS, build_session
from pipeline.models import ExtractionResult, PartnerEntryInfo


class SkaddenConnector(Connector):
    def __init__(self, firm_key, config, session=None):
        super().__init__(firm_key, config)
        self.session = session or build_session()

    def extract(self) -> ExtractionResult:
        records = []
        source_ids = set()
        profile_urls = set()
        offset = 0
        pages = 0
        total = None
        practice = self.config["practice_label"]
        while total is None or offset < total:
            payload, source_url = self._fetch(offset)
            reported = payload.get("ResultCount")
            rows = payload.get("SearchResults")
            if (
                type(reported) is not int or reported <= 0
                or (total is not None and reported != total)
                or not isinstance(rows, list) or not rows or offset + len(rows) > reported
            ):
                raise UnexpectedResponseError(f"Skadden returned inconsistent results at offset {offset}")
            total = reported
            for row in rows:
                if not isinstance(row, dict):
                    raise UnexpectedResponseError(f"Skadden returned a malformed row at offset {offset}")
                entry = self._parse_row(row, practice, source_url)
                if entry.source_record_id in source_ids or entry.profile_url in profile_urls:
                    raise UnexpectedResponseError(f"Skadden returned a duplicate profile at offset {offset}")
                records.append(entry)
                source_ids.add(entry.source_record_id)
                profile_urls.add(entry.profile_url)
            pages += 1
            offset += len(rows)
            if payload.get("HasMoreResults") is not (offset < total):
                raise UnexpectedResponseError(f"Skadden continuation disagreed with its total at offset {offset}")

        return ExtractionResult(
            firm_key=self.firm_key,
            records=records,
            expected_total=total,
            pages_fetched=pages,
            extraction_complete=True,
            scope_verified=False,
            covered_practices=[practice],
            missing_practices=["Broader Corporate and specialist M&A practices"],
        )

    def _fetch(self, offset):
        if offset:
            sleep(self.config["request_interval_seconds"])
        params = {
            "hasSearched": "true",
            "practice": self.config["practice_id"],
            "position": self.config["partner_position_id"],
            "skip": offset,
        }
        try:
            response = self.session.get(
                self.config["results_url"], params=params, timeout=DEFAULT_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
            selected = payload["SearchFilters"]["AllSelectedFilters"]
            selected_ids = {item["ID"] for item in selected if item["IsSelected"] is True}
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            raise ConnectorError(f"Skadden directory request failed at offset {offset}: {exc}") from exc
        if selected_ids != {params["practice"], params["position"]}:
            raise UnexpectedResponseError(f"Skadden did not confirm the requested filters at offset {offset}")
        return payload, response.url

    def _parse_row(self, row, practice, source_url):
        name, source_id, url, level = (row.get(key) for key in ("Name", "ID", "Url", "Level"))
        if not all(isinstance(value, str) and value.strip() for value in (name, source_id, url, level)):
            raise UnexpectedResponseError("Skadden returned a row without a name, ID, link or title")
        role = BeautifulSoup(level, "html.parser").get_text(" ", strip=True) if "<" in level else level.strip()
        if (
            row.get("IsRetiredPartner") is not False or row.get("IsDeceased") is not False
            or not re.search(r"\bpartner\b", role, re.IGNORECASE)
            or re.search(r"\b(?:retired|former)\b", role, re.IGNORECASE)
        ):
            raise UnexpectedResponseError(f"Skadden returned an unconfirmed active partner title: {role!r}")
        directory = self.config["directory_url"]
        profile = urlsplit(urljoin(directory, url))
        if (
            profile.scheme != "https" or profile.netloc != urlsplit(directory).netloc
            or not re.fullmatch(r"/professionals/[^/]+/[^/]+/?", profile.path, re.IGNORECASE)
        ):
            raise UnexpectedResponseError("Skadden returned an invalid profile link")
        offices = []
        for key in ("PrimaryOffice", "SecondaryOffice"):
            office = row.get(key)
            if isinstance(office, dict) and office.get("Name"):
                offices.append(office["Name"])
        primary_practice = row.get("PrimaryPractice")
        practices = [practice]
        if isinstance(primary_practice, str) and primary_practice.strip() and primary_practice != practice:
            practices.append(primary_practice)
        return PartnerEntryInfo(
            firm_key=self.firm_key, firm_name=self.config["name"], name=name.strip(),
            role=role, offices=offices, practices=practices, source_record_id=source_id.lower(),
            profile_url=profile._replace(path=profile.path.rstrip("/"), query="", fragment="").geturl(),
            source_url=source_url,
        )
