"""Connector-specific failures."""


class ConnectorError(RuntimeError):
    """Raised when a source cannot produce a trustworthy extraction."""


class UnexpectedResponseError(ConnectorError):
    """Raised when a source response no longer has the expected shape."""


class ProfileRateLimitError(ConnectorError):
    """Raised when a profile source returns HTTP 429."""

    def __init__(self, message: str, retry_after: str | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after
