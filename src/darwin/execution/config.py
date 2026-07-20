from decimal import Decimal

from pydantic import BaseModel, Field


class ExecutionSimulationConfig(BaseModel):
    fill_model: str = "marketable"
    submission_latency_ms: int = 100
    cancellation_latency_ms: int = 100
    exchange_processing_latency_ms: int = 25
    network_latency_ms: int = 25
    slippage_bps: int = 5
    max_book_participation: Decimal = Decimal("0.5")
    random_seed: int = 42
    order_expiration_seconds: int = 5
    repricing_interval_seconds: int = 2
    maximum_order_age_seconds: int = 10
