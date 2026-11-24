"""One configuration-driven HTML profile connector for supported firms."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace
from datetime import datetime, timezone
from time import monotonic, sleep
from typing import Any

import requests
from bs4 import BeautifulSoup, Tag

from pipeline.connectors.errors import ConnectorError, ProfileRateLimitError, UnexpectedResponseError
from pipeline.connectors.http import DEFAULT_TIMEOUT_SECONDS, build_session
from pipeline.models import PartnerEntryInfo, PartnerProfileInfo
from pipeline.profile_enrichment.base import ProfileConnector


class ConfiguredHtmlProfileConnector(ProfileConnector):
    def __init__(
        self,
        sources: dict[str, dict[str, Any]],
        session: requests.Session | None = None,
    ) -> None:
        self.sources = sources
        self.session = session or build_session()
        self.paced_session = session
        self.last_request_finished: dict[str, float] = {}

    def enrich(self, entry: PartnerEntryInfo) -> PartnerProfileInfo:
        config = self.sources.get(entry.firm_key)
        if config is None:
            raise ConnectorError(
                f"No profile parser configuration for '{entry.firm_key}'"
            )
        interval = config.get("request_interval_seconds", 0)
        session = self.session
        if interval:
            if self.paced_session is None:
                self.paced_session = build_session(retry_rate_limits=False)
            session = self.paced_session
            previous = self.last_request_finished.get(entry.firm_key)
            if previous is not None:
                sleep(max(0, interval - (monotonic() - previous)))
        try:
            response = session.get(
                entry.profile_url,
                timeout=DEFAULT_TIMEOUT_SECONDS,
            )
            if interval and response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                detail = f" (Retry-After: {retry_after})" if retry_after else ""
                raise ProfileRateLimitError(f"HTTP 429 fetching {entry.profile_url}{detail}", retry_after)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ConnectorError(
                f"Profile request failed for {entry.profile_url}: {exc}"
            ) from exc
        finally:
            if interval:
                self.last_request_finished[entry.firm_key] = monotonic()

        content_type = response.headers.get("Content-Type", "").lower()
        if "html" not in content_type:
            raise UnexpectedResponseError(
                f"Profile returned {content_type or 'an unknown content type'}, not HTML"
            )
        return self.parse(entry, response.content, config)

    def parse(
        self,
        entry: PartnerEntryInfo,
        html: str | bytes,
        config: dict[str, Any] | None = None,
    ) -> PartnerProfileInfo:
        config = config or self.sources.get(entry.firm_key)
        if config is None:
            raise ConnectorError(
                f"No profile parser configuration for '{entry.firm_key}'"
            )
        soup = BeautifulSoup(html, "html.parser")
        selectors = config.get("selectors", {})

        parsed_name = self._one(soup, selectors.get("name"))
        if parsed_name and not self._same_name(parsed_name, entry.name):
            raise UnexpectedResponseError(
                f"Profile name '{parsed_name}' does not match directory name '{entry.name}'"
            )

        role = self._one(soup, selectors.get("role")) or entry.role or None
        biography = self._one(soup, selectors.get("biography")) or None
        offices = self._merge(entry.offices, self._many(soup, selectors.get("offices")))
        practices = self._merge(
            entry.practices, self._many(soup, selectors.get("practices"))
        )
        phones = self._many(soup, selectors.get("phone_numbers"))
        email = self._one(soup, selectors.get("email")) or None

        if not biography:
            raise UnexpectedResponseError(
                f"Profile parser found no biography at {entry.profile_url}"
            )
        profile = PartnerProfileInfo(
            firm_key=entry.firm_key,
            partner_entry_id=entry.partner_entry_id,
            name=parsed_name or entry.name,
            profile_url=entry.profile_url,
            role=role,
            offices=offices,
            practices=practices,
            biography=biography,
            phone_numbers=phones,
            email=email,
            education=self._many(soup, selectors.get("education")),
            admissions=self._many(soup, selectors.get("admissions")),
            languages=self._many(soup, selectors.get("languages")),
            source_checked_at=datetime.now(timezone.utc).isoformat(),
            content_hash="",
        )
        return with_content_hash(profile)

    @classmethod
    def _one(cls, soup: BeautifulSoup, spec: Any) -> str:
        values = cls._many(soup, spec)
        return values[0] if values else ""

    @classmethod
    def _many(cls, soup: BeautifulSoup, spec: Any) -> list[str]:
        if not spec:
            return []
        specs = spec if isinstance(spec, list) else [spec]
        values: list[str] = []
        for item in specs:
            if isinstance(item, str):
                item = {"selector": item}
            if not isinstance(item, dict) or not item.get("selector"):
                continue
            attribute = item.get("attribute")
            for node in soup.select(str(item["selector"])):
                if not isinstance(node, Tag):
                    continue
                raw = node.get(str(attribute)) if attribute else node.get_text(" ", strip=True)
                value = cls._clean(raw)
                prefix = str(item.get("strip_prefix", ""))
                if prefix and value.casefold().startswith(prefix.casefold()):
                    value = value[len(prefix) :].strip()
                if value and value not in values:
                    values.append(value)
        return values

    @staticmethod
    def _merge(existing: list[str], extracted: list[str]) -> list[str]:
        return list(dict.fromkeys([*existing, *extracted]))

    @staticmethod
    def _same_name(left: str, right: str) -> bool:
        def normalize(value: str) -> str:
            return "".join(
                character.casefold() for character in value if character.isalnum()
            )

        return normalize(left) == normalize(right)

    @staticmethod
    def _clean(value: Any) -> str:
        return " ".join(str(value or "").split())


def with_content_hash(profile: PartnerProfileInfo) -> PartnerProfileInfo:
    content = asdict(profile)
    for key in ("firm_key", "partner_entry_id", "name", "profile_url", "source_checked_at", "content_hash"):
        del content[key]
    canonical_text = json.dumps(content, sort_keys=True, ensure_ascii=False)
    return replace(profile, content_hash=hashlib.sha256(canonical_text.encode("utf-8")).hexdigest())
