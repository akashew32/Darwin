from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from darwin.domain.enums import BookSide, Exchange, MarketStatus, OrderIntent, OutcomeSide
from darwin.domain.fill import Fill
from darwin.domain.market import Event, Market, Outcome
from darwin.domain.orderbook import OrderBookDelta, OrderBookSnapshot, PriceLevel


def cents_to_probability(cents: int | str | Decimal) -> Decimal:
    return Decimal(str(cents)) / Decimal("100")


def probability_to_cents(price: Decimal) -> int:
    return int((price * Decimal("100")).to_integral_value())


def kalshi_status(value: str | None) -> MarketStatus:
    mapping = {
        "unopened": MarketStatus.UNOPENED,
        "open": MarketStatus.OPEN,
        "paused": MarketStatus.PAUSED,
        "closed": MarketStatus.CLOSED,
        "settled": MarketStatus.SETTLED,
        "finalized": MarketStatus.RESOLVED,
        "resolved": MarketStatus.RESOLVED,
    }
    return mapping.get((value or "").lower(), MarketStatus.CLOSED)


def _parse_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(UTC)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)


def map_event(raw: dict[str, Any]) -> Event:
    return Event(
        exchange=Exchange.KALSHI,
        event_id=str(raw.get("event_ticker") or raw.get("ticker")),
        title=str(raw.get("title") or ""),
        category=raw.get("category"),
        close_time=_parse_ts(raw.get("close_time")),
    )


def map_market(raw: dict[str, Any]) -> Market:
    return Market(
        exchange=Exchange.KALSHI,
        market_id=str(raw.get("ticker")),
        event_id=str(raw.get("event_ticker") or ""),
        title=str(raw.get("title") or raw.get("subtitle") or raw.get("ticker")),
        status=kalshi_status(raw.get("status")),
        outcomes=(
            Outcome(side=OutcomeSide.YES, label="YES"),
            Outcome(side=OutcomeSide.NO, label="NO"),
        ),
        close_time=_parse_ts(raw.get("close_time")),
        category=raw.get("category"),
    )


def map_orderbook(market_id: str, raw: dict[str, Any], received_ts: datetime) -> OrderBookSnapshot:
    book = raw.get("orderbook_fp") or raw.get("orderbook") or raw
    yes = book.get("yes_dollars") or book.get("yes_dollars_fp") or book.get("yes") or []
    no = book.get("no_dollars") or book.get("no_dollars_fp") or book.get("no") or []
    bids = tuple(
        sorted(
            (
                PriceLevel(price=_level_price(level[0]), quantity=int(Decimal(str(level[1]))))
                for level in yes
            ),
            key=lambda level: level.price,
            reverse=True,
        )
    )
    asks = tuple(
        sorted(
            (
                PriceLevel(
                    price=Decimal("1") - _level_price(level[0]),
                    quantity=int(Decimal(str(level[1]))),
                )
                for level in no
            ),
            key=lambda level: level.price,
        )
    )
    return OrderBookSnapshot(
        exchange=Exchange.KALSHI,
        market_id=market_id,
        bids=bids,
        asks=asks,
        sequence=raw.get("seq"),
        received_ts=received_ts,
    )


def map_delta(raw: dict[str, Any], received_ts: datetime) -> OrderBookDelta:
    msg = raw.get("msg", raw)
    market_id = str(msg.get("market_ticker") or msg.get("ticker"))
    side = OutcomeSide.YES if str(msg.get("side", "yes")).lower() == "yes" else OutcomeSide.NO
    price = _level_price(msg.get("price_dollars") or msg.get("price"))
    if side == OutcomeSide.NO:
        price = Decimal("1") - price
        book_side = BookSide.ASK
    else:
        book_side = BookSide.BID
    return OrderBookDelta(
        exchange=Exchange.KALSHI,
        market_id=market_id,
        side=book_side,
        outcome=OutcomeSide.YES,
        price=price,
        delta_quantity=int(Decimal(str(msg.get("delta_fp", msg.get("delta", 0))))),
        absolute_quantity=msg.get("quantity"),
        sequence=raw.get("seq"),
        received_ts=received_ts,
    )


def _level_price(value: Any) -> Decimal:
    decimal = Decimal(str(value))
    if decimal > 1:
        return cents_to_probability(decimal)
    return decimal


def map_fill(raw: dict[str, Any], received_ts: datetime) -> Fill:
    raw_price = raw.get("price")
    raw_quantity = raw.get("count") or raw.get("quantity")
    if raw_price is None or raw_quantity is None:
        raise ValueError("fill payload requires price and quantity")
    return Fill(
        exchange=Exchange.KALSHI,
        fill_id=str(raw.get("trade_id") or raw.get("fill_id")),
        market_id=str(raw.get("ticker") or raw.get("market_ticker")),
        client_order_id=str(raw.get("client_order_id") or ""),
        exchange_order_id=raw.get("order_id"),
        outcome=OutcomeSide.YES
        if str(raw.get("yes_no", "yes")).lower() == "yes"
        else OutcomeSide.NO,
        intent=OrderIntent.BUY
        if str(raw.get("action", "buy")).lower() == "buy"
        else OrderIntent.SELL,
        price=cents_to_probability(raw_price),
        quantity=int(raw_quantity),
        fee=Decimal(str(raw.get("fee", 0))) / Decimal("100"),
        exchange_ts=_parse_ts(raw.get("created_time")),
        received_ts=received_ts,
    )
