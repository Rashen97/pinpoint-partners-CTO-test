"""Collect selected Corporate capabilities from King & Spalding's People search."""

import json
import re
from math import ceil
from time import sleep
from urllib.parse import urljoin, urlsplit

import requests

from pipeline.connectors.base import Connector
from pipeline.connectors.errors import ConnectorError, UnexpectedResponseError
from pipeline.connectors.http import DEFAULT_TIMEOUT_SECONDS, build_session
from pipeline.models import ExtractionResult, PartnerEntryInfo
from pipeline.processing.deduplicate import deduplicate_records


class KingSpaldingConnector(Connector):
    def __init__(self, firm_key, config, session=None):
        super().__init__(firm_key, config)
        self.session = session or build_session()

    def extract(self) -> ExtractionResult:
        records = []
        pages_fetched = 0
        capabilities = self.config["capability_filters"]
        page_size = self.config["page_size"]
        for capability in capabilities:
            profiles = set()
            page = 1
            total = None
            while total is None or len(profiles) < total:
                if pages_fetched:
                    sleep(self.config["request_interval_seconds"])
                payload = self._fetch(capability, page)
                reported = payload.get("totalHits")
                hits = payload.get("hits")
                if (
                    type(reported) is not int or reported <= 0
                    or (total is not None and reported != total)
                    or payload.get("page") != page or payload.get("pageSize") != page_size
                    or payload.get("totalPages") != ceil(reported / page_size)
                    or not isinstance(hits, list)
                    or len(hits) != min(page_size, reported - len(profiles))
                ):
                    raise UnexpectedResponseError(f"King & Spalding {capability} returned inconsistent results on page {page}")
                total = reported
                for hit in hits:
                    entry = self._parse_hit(hit, capability)
                    if entry.profile_url in profiles:
                        raise UnexpectedResponseError(f"King & Spalding {capability} repeated a profile on page {page}")
                    profiles.add(entry.profile_url)
                    records.append(entry)
                page += 1
                pages_fetched += 1

        unique = deduplicate_records(records)
        return ExtractionResult(
            firm_key=self.firm_key,
            records=unique,
            expected_total=len(unique),
            pages_fetched=pages_fetched,
            extraction_complete=True,
            scope_verified=False,
            covered_practices=list(capabilities),
            missing_practices=["Full Corporate practice group roster"],
        )

    def _fetch(self, capability, page):
        body = {
            "SearchText": None,
            "Page": page,
            "PageSize": self.config["page_size"],
            "Categories": ["people"],
            "SelectedFilters": {
                "Title": self.config["partner_titles"],
                "Capability": [capability],
            },
            "Language": "en",
        }
        try:
            response = self.session.post(
                self.config["results_url"], json=body, timeout=DEFAULT_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise ConnectorError(f"King & Spalding search failed on page {page} for {capability}: {exc}") from exc
        if not isinstance(payload, dict):
            raise UnexpectedResponseError(f"King & Spalding returned a malformed response for {capability}")
        return payload

    def _parse_hit(self, hit, capability):
        metadata = hit.get("metadata") if isinstance(hit, dict) else None
        if not isinstance(metadata, dict) or hit.get("category") != "people":
            raise UnexpectedResponseError(f"King & Spalding {capability} returned a malformed person result")
        name = metadata.get("PersonName")
        role = metadata.get("BusinessTitle")
        url = hit.get("url")
        if (
            not isinstance(name, str) or not name.strip() or not isinstance(url, str)
            or role not in self.config["partner_titles"]
        ):
            raise UnexpectedResponseError(f"King & Spalding {capability} returned an unconfirmed partner")
        directory = self.config["directory_url"]
        profile = urlsplit(urljoin(directory, url))
        path = profile.path.rstrip("/")
        if (
            profile.scheme != "https" or profile.netloc != urlsplit(directory).netloc
            or not re.fullmatch(r"/people/[^/]+", path)
        ):
            raise UnexpectedResponseError(f"King & Spalding {capability} returned an invalid profile URL")
        offices_json = metadata.get("OfficesJson")
        try:
            offices = json.loads(offices_json) if offices_json else []
        except (ValueError, TypeError) as exc:
            raise UnexpectedResponseError(f"King & Spalding {capability} returned malformed offices") from exc
        if not isinstance(offices, list) or any(
            not isinstance(office, dict) or not isinstance(office.get("Name"), str)
            for office in offices
        ):
            raise UnexpectedResponseError(f"King & Spalding {capability} returned malformed office records")
        primary = metadata.get("Capabilities")
        practices = [capability]
        if isinstance(primary, str) and primary.strip() and primary != capability:
            practices.append(primary)
        return PartnerEntryInfo(
            firm_key=self.firm_key, firm_name=self.config["name"], name=" ".join(name.split()),
            role=role, offices=[office["Name"] for office in offices], practices=practices,
            profile_url=profile._replace(path=path, query="", fragment="").geturl(),
            source_url=directory,
        )
