"""Present firm office values as consistent city or region labels."""

import re
import unicodedata


OFFICE_LABELS = (
    "Abu Dhabi", "Atlanta", "Austin", "Beijing", "Boston", "Brussels",
    "Century City", "Charlotte", "Chicago", "Dallas", "Denver", "Dubai",
    "Düsseldorf", "Frankfurt", "Hamburg", "Hong Kong", "Houston", "London",
    "Los Angeles", "Madrid", "Melbourne", "Miami", "Milan", "Munich",
    "New York", "Northern California", "Northern Virginia", "Orange County",
    "Palo Alto", "Paris", "Riyadh", "San Diego", "San Francisco", "São Paulo",
    "Seoul", "Silicon Valley", "Singapore", "Sydney", "Tel Aviv", "Tokyo",
    "Toronto", "Washington, D.C.", "Wilmington", "Zurich",
)


def _matching_text(value: str) -> str:
    plain = "".join(
        char for char in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(char)
    )
    return " ".join(re.findall(r"\w+", plain))


_LABELS = {_matching_text(label): label for label in OFFICE_LABELS}
_LABELS.update({
    "bruxelles": "Brussels",
    "new york city": "New York",
    "nyc": "New York",
    "washington dc": "Washington, D.C.",
})
_CITY_IN_ADDRESS = re.compile(
    r"\b(?:" + "|".join(map(re.escape, sorted(_LABELS, key=len, reverse=True))) + r")\b"
)
_OFFICE_SEPARATOR = re.compile(r"\s+(?:and|&)\s+|[;/]", re.IGNORECASE)


def normalise_offices(offices: list[str]) -> list[str]:
    labels = []
    for office in offices:
        parts = [_matching_text(part) for part in _OFFICE_SEPARATOR.split(office)]
        if all(part in _LABELS for part in parts):
            labels.extend(_LABELS[part] for part in parts)
            continue
        # The city follows the street and building details in the saved addresses.
        matches = _CITY_IN_ADDRESS.findall(_matching_text(office))
        if matches:
            labels.append(_LABELS[matches[-1]])
    return list(dict.fromkeys(labels))
