from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from darwin.domain.enums import OutcomeSide, RiskDecisionType
from darwin.domain.order import OrderRequest


class FeatureVector(BaseModel):
    model_config = ConfigDict(frozen=True)

    market_id: str
    asof_ts: datetime
    values: dict[str, float]


class Signal(BaseModel):
    model_config = ConfigDict(frozen=True)

    market_id: str
    asof_ts: datetime
    outcome: OutcomeSide | None
    score: float
    expected_edge: Decimal
    action: str
    reasons: tuple[str, ...] = Field(default_factory=tuple)
    order: OrderRequest | None = None


class StrategyDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    market_id: str
    asof_ts: datetime
    action: str
    target_yes_position: int
    score: float
    estimated_fair_value: Decimal
    estimated_executable_price: Decimal
    gross_edge: Decimal
    estimated_fees: Decimal
    estimated_slippage: Decimal
    net_edge: Decimal
    reasons: tuple[str, ...] = Field(default_factory=tuple)
    proposed_orders: tuple[OrderRequest, ...] = Field(default_factory=tuple)


class RiskDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision: RiskDecisionType
    asof_ts: datetime
    order: OrderRequest | None = None
    reasons: tuple[str, ...] = Field(default_factory=tuple)
