class KalshiError(Exception):
    """Base Kalshi adapter error."""


class KalshiAuthenticationError(KalshiError):
    """Raised when authenticated features are requested without credentials."""


class KalshiRateLimitError(KalshiError):
    """Raised when Kalshi rate limits a request."""


class KalshiSequenceGap(KalshiError):
    """Raised when WebSocket sequence validation detects a gap."""
