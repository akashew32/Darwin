from enum import StrEnum


class Exchange(StrEnum):
    KALSHI = "kalshi"


class MarketStatus(StrEnum):
    UNOPENED = "unopened"
    OPEN = "open"
    PAUSED = "paused"
    CLOSED = "closed"
    SETTLED = "settled"
    RESOLVED = "resolved"


class OutcomeSide(StrEnum):
    YES = "yes"
    NO = "no"


class OrderIntent(StrEnum):
    BUY = "buy"
    SELL = "sell"


class BookSide(StrEnum):
    BID = "bid"
    ASK = "ask"


class OrderStatus(StrEnum):
    CREATED = "created"
    PENDING_SUBMISSION = "pending_submission"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    PENDING_CANCELLATION = "pending_cancellation"
    CANCELED = "canceled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    UNKNOWN_PENDING_RECONCILIATION = "unknown_pending_reconciliation"


class RiskDecisionType(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    KILL_SWITCH = "kill_switch"


class TradingMode(StrEnum):
    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE = "live"
