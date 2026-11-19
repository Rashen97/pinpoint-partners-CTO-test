"""Connector-specific failures."""


class ConnectorError(RuntimeError):
    """Raised when a source cannot produce a trustworthy extraction."""


class UnexpectedResponseError(ConnectorError):
    """Raised when a source response no longer has the expected shape."""
