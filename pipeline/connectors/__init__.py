"""Firm connector registry."""

from __future__ import annotations

from typing import Any

from pipeline.connectors.base import Connector
from pipeline.connectors.kirkland import KirklandConnector
from pipeline.connectors.paul_weiss import PaulWeissConnector
from pipeline.connectors.simpson_thacher import SimpsonThacherConnector
from pipeline.connectors.sullivan_cromwell import SullivanCromwellConnector
from pipeline.connectors.wachtell_lipton import WachtellLiptonConnector


CONNECTORS: dict[str, type[Connector]] = {
    "kirkland": KirklandConnector,
    "paul_weiss": PaulWeissConnector,
    "simpson_thacher": SimpsonThacherConnector,
    "sullivan_cromwell": SullivanCromwellConnector,
    "wachtell_lipton": WachtellLiptonConnector,
}


def build_connector(firm_key: str, config: dict[str, Any]) -> Connector:
    try:
        connector_class = CONNECTORS[firm_key]
    except KeyError as exc:
        raise NotImplementedError(f"No connector implemented for '{firm_key}'") from exc
    return connector_class(firm_key=firm_key, config=config)
