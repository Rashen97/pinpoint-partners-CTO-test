"""Cravath public partner search."""

from urllib.parse import urljoin, urlsplit

import requests

from pipeline.connectors.base import Connector
from pipeline.connectors.errors import ConnectorError, UnexpectedResponseError
from pipeline.connectors.http import DEFAULT_TIMEOUT_SECONDS, build_session
from pipeline.models import ExtractionResult, PartnerEntryInfo
from pipeline.processing.deduplicate import deduplicate_records


class CravathConnector(Connector):
    def __init__(self, firm_key, config, session=None):
        super().__init__(firm_key, config)
        self.session = session or build_session()

    def extract(self) -> ExtractionResult:
        endpoint = self.config["results_url"]
        filters = self.config["practice_filters"]
        records = []
        for practice in filters:
            try:
                response = self.session.get(
                    endpoint, params={"v": "partner", "pr": practice["id"]},
                    timeout=DEFAULT_TIMEOUT_SECONDS,
                )
                response.raise_for_status()
                bucket = response.json()["hits"]["ALL"]
                rows = bucket["hits"]
                if not isinstance(rows, list) or not rows or len(rows) != bucket["total"]:
                    raise ValueError("partner results do not match the reported total")
                batch = [self._parse_row(row, practice, response.url) for row in rows]
                if len({entry.profile_url for entry in batch}) != len(batch):
                    raise ValueError("partner results contain duplicate profile URLs")
            except requests.RequestException as exc:
                raise ConnectorError(f"Cravath {practice['label']} request failed: {exc}") from exc
            except (KeyError, TypeError, ValueError) as exc:
                raise UnexpectedResponseError(f"Invalid Cravath {practice['label']} results: {exc}") from exc
            records.extend(batch)

        return ExtractionResult(
            firm_key=self.firm_key,
            records=deduplicate_records(records),
            pages_fetched=len(filters),
            extraction_complete=True,
            scope_verified=True,
            covered_practices=[practice["label"] for practice in filters],
        )

    def _parse_row(self, row, practice, source_url) -> PartnerEntryInfo:
        content = row["content_data"]
        role = content["position"]["name"]
        practices = content["practices"]
        offices = content["offices_info-office_information-office"]
        profile_url = urljoin(self.config["directory_url"], row["url"])
        profile = urlsplit(profile_url)
        if (
            role != "Partner"
            or not row["name"].strip()
            or profile.hostname != urlsplit(self.config["directory_url"]).hostname
            or not profile.path.startswith("/people/")
            or not profile.path.endswith(".html")
            or not offices
            or practice["id"] not in {item["id"] for item in practices}
        ):
            raise ValueError("row does not match the requested partner practice")
        return PartnerEntryInfo(
            firm_key=self.firm_key,
            firm_name=self.config["name"],
            name=row["name"],
            role=role,
            offices=[office["name"] for office in offices],
            practices=[item["name"] for item in practices],
            profile_url=profile_url,
            source_url=source_url,
            source_record_id=str(row["id"]),
        )
