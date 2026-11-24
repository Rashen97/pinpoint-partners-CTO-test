"""Firm connector registry."""

from __future__ import annotations

from typing import Any

from pipeline.connectors.base import Connector
from pipeline.connectors.cravath import CravathConnector
from pipeline.connectors.davis_polk import DavisPolkConnector
from pipeline.connectors.gibson_dunn import GibsonDunnConnector
from pipeline.connectors.king_spalding import KingSpaldingConnector
from pipeline.connectors.kirkland import KirklandConnector
from pipeline.connectors.latham_watkins import LathamWatkinsConnector
from pipeline.connectors.milbank import MilbankConnector
from pipeline.connectors.paul_hastings import PaulHastingsConnector
from pipeline.connectors.paul_weiss import PaulWeissConnector
from pipeline.connectors.quinn_emanuel import QuinnEmanuelConnector
from pipeline.connectors.simpson_thacher import SimpsonThacherConnector
from pipeline.connectors.skadden import SkaddenConnector
from pipeline.connectors.sullivan_cromwell import SullivanCromwellConnector
from pipeline.connectors.wachtell_lipton import WachtellLiptonConnector
from pipeline.connectors.weil import WeilConnector


CONNECTORS: dict[str, type[Connector]] = {
    "cravath": CravathConnector,
    "davis_polk": DavisPolkConnector,
    "gibson_dunn": GibsonDunnConnector,
    "king_spalding": KingSpaldingConnector,
    "kirkland": KirklandConnector,
    "latham_watkins": LathamWatkinsConnector,
    "milbank": MilbankConnector,
    "paul_hastings": PaulHastingsConnector,
    "paul_weiss": PaulWeissConnector,
    "quinn_emanuel": QuinnEmanuelConnector,
    "simpson_thacher": SimpsonThacherConnector,
    "skadden": SkaddenConnector,
    "sullivan_cromwell": SullivanCromwellConnector,
    "wachtell_lipton": WachtellLiptonConnector,
    "weil": WeilConnector,
}


def build_connector(firm_key: str, config: dict[str, Any]) -> Connector:
    try:
        connector_class = CONNECTORS[firm_key]
    except KeyError as exc:
        raise NotImplementedError(f"No connector implemented for '{firm_key}'") from exc
    return connector_class(firm_key=firm_key, config=config)
