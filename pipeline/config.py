"""Configuration loading for firm sources."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


CONFIG_PATH = Path(__file__).with_name("firms.yaml")


def load_firms(path: Path = CONFIG_PATH) -> dict[str, dict[str, Any]]:
    with path.open(encoding="utf-8") as config_file:
        data = yaml.safe_load(config_file)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a mapping in {path}")
    return data
