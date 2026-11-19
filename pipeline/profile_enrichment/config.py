"""Load selector configuration for the shared profile parser."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


PROFILE_CONFIG_PATH = Path(__file__).with_name("profile_sources.yaml")


def load_profile_sources(
    path: Path = PROFILE_CONFIG_PATH,
) -> dict[str, dict[str, Any]]:
    with path.open(encoding="utf-8") as config_file:
        data = yaml.safe_load(config_file)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a mapping in {path}")
    return data
