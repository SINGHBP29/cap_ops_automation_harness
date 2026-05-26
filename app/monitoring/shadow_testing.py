from fastapi import APIRouter
from fastapi import HTTPException

from app.services.shadow_testing_service import build_shadow_test_report

router = APIRouter()


@router.get("/shadow-test")
async def shadow_test(query: str | None = None):
    try:
        queries = [query] if query and query.strip() else None
        return await build_shadow_test_report(queries=queries)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
