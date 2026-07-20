from fastapi import APIRouter

router = APIRouter(prefix="/markets", tags=["markets"])


@router.get("")
def list_markets() -> list[dict[str, str]]:
    return []
