from fastapi import APIRouter

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("")
def metrics() -> dict[str, int]:
    return {"orders_submitted": 0, "risk_rejections": 0, "fills": 0}
