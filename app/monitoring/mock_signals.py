from fastapi import APIRouter
from fastapi import HTTPException

from app.services.mock_signal_service import MockSignalService

router = APIRouter()
service = MockSignalService()


@router.get("/mock-signals/scenarios")
async def mock_signal_scenarios():
    return service.list_scenarios()


@router.post("/mock-signals/generate/{scenario_name}")
async def generate_mock_signal(scenario_name: str, derive_signals: bool = True):
    try:
        return await service.generate_scenario(scenario_name, derive_signals=derive_signals)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown mock signal scenario '{scenario_name}'.") from exc
