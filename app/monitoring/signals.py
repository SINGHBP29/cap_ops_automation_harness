from fastapi import APIRouter

from app.services.ops_ledger import list_signals
from app.services.ops_ledger import ledger_snapshot

router = APIRouter()


@router.get("/signals")
async def get_signals(origin: str | None = None):
    if origin is None:
        snapshot = ledger_snapshot()
        return {
            "recent_signals": snapshot["recent_signals"],
            "signal_count": snapshot["signal_count"],
            "signal_counts_by_origin": snapshot["signal_counts_by_origin"],
        }
    filtered = list_signals(origin)
    return {
        "recent_signals": filtered,
        "signal_count": len(filtered),
        "origin": origin,
    }


@router.get("/signals/api-generated")
async def get_api_generated_signals():
    filtered = list_signals("api_generated")
    return {
        "recent_signals": filtered,
        "signal_count": len(filtered),
        "origin": "api_generated",
    }


@router.get("/signals/mock-generated")
async def get_mock_generated_signals():
    filtered = list_signals("mock_data")
    return {
        "recent_signals": filtered,
        "signal_count": len(filtered),
        "origin": "mock_data",
    }


@router.get("/signals/ops-ingested")
async def get_ops_ingested_signals():
    filtered = list_signals("ops_api")
    return {
        "recent_signals": filtered,
        "signal_count": len(filtered),
        "origin": "ops_api",
    }
