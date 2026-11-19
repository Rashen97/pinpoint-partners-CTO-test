"""Stable identity helpers for unified partner roster entries."""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit
from uuid import UUID, uuid5


PARTNER_ENTRY_NAMESPACE = UUID("942e5c1a-cbc6-4be1-bc6d-fcae58dced1a")


def canonicalize_profile_url(profile_url: str) -> str:
    """Normalize stable URL components used by identity and deduplication."""
    value = profile_url.strip()
    parts = urlsplit(value)
    scheme = parts.scheme.casefold()
    hostname = (parts.hostname or "").casefold()
    port = parts.port
    if port and not ((scheme == "https" and port == 443) or (scheme == "http" and port == 80)):
        netloc = f"{hostname}:{port}"
    else:
        netloc = hostname
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((scheme, netloc, path, parts.query, ""))


def create_partner_entry_id(firm_key: str, profile_url: str) -> str:
    canonical_url = canonicalize_profile_url(profile_url)
    return str(uuid5(PARTNER_ENTRY_NAMESPACE, f"{firm_key}|{canonical_url}"))
