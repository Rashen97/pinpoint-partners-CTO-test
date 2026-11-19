"""Gibson Dunn's public Partner search across selected practices."""

import json
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


class GibsonDunnConnector(Connector):
    def __init__(self, firm_key, config, session=None):
        super().__init__(firm_key, config)
        self.session = session or build_session()

    def extract(self) -> ExtractionResult:
        source = self.config["filtered_url"]
        try:
            directory = self.session.get(source, timeout=DEFAULT_TIMEOUT_SECONDS)
            directory.raise_for_status()
        except requests.RequestException as exc:
            raise ConnectorError(f"Gibson Dunn directory request failed: {exc}") from exc
        soup = BeautifulSoup(directory.content, "html.parser")
        facets = soup.select('.wpgb-facet[data-grid="archivePeople"][data-facet]')
        if not facets:
            raise UnexpectedResponseError("Gibson Dunn directory returned no search facets")
        settings = {
            "id": "archivePeople",
            "is_template": True,
            "is_main_query": False,
            "main_query": [],
            "permalink": self.config["directory_url"],
            "lang": "",
            "facets": list(dict.fromkeys(int(facet["data-facet"]) for facet in facets)),
        }
        all_records = []
        covered = []
        warnings = ["The published evidence does not establish a complete global Corporate practice list."]
        filters = self.config["practice_filters"]
        pages_fetched = 0
        for practice in filters:
            try:
                records, pages = self._extract_practice(settings, practice)
            except UnexpectedResponseError as exc:
                if not covered:
                    raise
                warnings.append(f"{practice['label']}: {exc}")
                continue
            except ConnectorError as exc:
                if not covered:
                    raise
                warnings.append(f"{practice['label']}: {exc}")
                break
            all_records.extend(records)
            covered.append(practice["label"])
            pages_fetched += pages
        return ExtractionResult(
            firm_key=self.firm_key,
            records=deduplicate_records(all_records),
            pages_fetched=pages_fetched,
            extraction_complete=True,
            scope_verified=False,
            covered_practices=covered,
            missing_practices=[
                "Full Corporate scope",
                *[practice["label"] for practice in filters if practice["label"] not in covered],
            ],
            warnings=warnings,
        )

    def _extract_practice(self, settings, practice) -> tuple[list[PartnerEntryInfo], int]:
        source = self.config["directory_url"] + "?" + urlencode({"_people_practices": practice["slug"]})
        records = {}
        pages = 0
        total = None
        while total is None or len(records) < total:
            sleep(self.config.get("request_interval_seconds", 0))
            payload = self._fetch(settings, len(records), practice["slug"])
            reported = payload.get("total")
            html = payload.get("posts")
            if type(reported) is not int or reported <= 0 or not isinstance(html, str):
                raise UnexpectedResponseError("Gibson Dunn returned an invalid result count or cards")
            if total is not None and total != reported:
                raise UnexpectedResponseError("Gibson Dunn's reported total changed during pagination")
            total = reported
            cards = BeautifulSoup(html, "html.parser").select(".people")
            if not cards or len(records) + len(cards) > total:
                raise UnexpectedResponseError("Gibson Dunn batch did not match the reported total")
            for card in cards:
                entry = self._parse_card(card, source, practice["label"])
                if entry.profile_url in records:
                    raise UnexpectedResponseError("Gibson Dunn returned a duplicate profile")
                records[entry.profile_url] = entry
            pages += 1
        return [entry for entry in records.values() if self._is_partner(entry.role)], pages

    def _fetch(self, settings, offset, practice_slug):
        filters = {
            "people_practices": practice_slug,
            "people_title": "000_partner",
        }
        params = {f"_{key}": value for key, value in filters.items()}
        if offset:
            params["_people_load_more"] = offset
        try:
            response = self.session.post(
                self.config["results_url"], params=params,
                files={"wpgb": (None, json.dumps(settings))}, timeout=DEFAULT_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
            selected = {
                facet.get("slug"): facet.get("selected") for facet in payload["facets"].values()
            }
        except (requests.RequestException, ValueError, KeyError, AttributeError, TypeError) as exc:
            raise ConnectorError(f"Gibson Dunn search at offset {offset} failed: {exc}") from exc
        if any(selected.get(key) != [value] for key, value in filters.items()):
            raise UnexpectedResponseError("Gibson Dunn did not confirm the selected practice and title")
        return payload

    def _parse_card(self, card, source, practice) -> PartnerEntryInfo:
        link = card.select_one('a[href*="/lawyer/"]:has(.name)')
        title = card.select_one(".title span")
        if link is None or title is None:
            raise UnexpectedResponseError("Gibson Dunn card is missing a profile link or title")
        name = link.select_one(".name").get_text(" ", strip=True)
        role = title.get_text(" ", strip=True)
        profile = urlsplit(urljoin(source, link["href"]))
        if (
            not name or not role
            or profile.scheme != "https" or profile.netloc != urlsplit(source).netloc
            or not re.fullmatch(r"/lawyer/[^/]+/?", profile.path)
        ):
            raise UnexpectedResponseError("Gibson Dunn returned a card with an invalid name, title or link")
        card_practices = [
            node.get_text(" ", strip=True) for node in card.select('.title a[href*="/practice/"]')
        ]
        contact = card.select_one(".contact-details")
        offices = [
            value.strip() for value in contact.find_all(string=True, recursive=False)
            if value.strip() and value.strip() != "T:"
        ] if contact else []
        return PartnerEntryInfo(
            firm_key=self.firm_key,
            firm_name=self.config["name"],
            name=name,
            role=role,
            offices=offices,
            practices=list(dict.fromkeys([practice, *card_practices])),
            profile_url=profile._replace(
                path=profile.path.rstrip("/") + "/", query="", fragment=""
            ).geturl(),
            source_url=source,
        )

    @staticmethod
    def _is_partner(role: str) -> bool:
        return bool(re.search(r"\bPartner\b", role)) and not re.search(
            r"\b(?:Former|Retired) Partner\b", role, re.IGNORECASE
        )
