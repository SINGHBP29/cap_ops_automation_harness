from fastapi import APIRouter

from app.models.capability_signal import CapabilitySignalEvent
from app.services.capability_signal_engine import capability_signal_rules
from app.services.capability_signal_engine import evaluate_capability_signal_event

router = APIRouter()


@router.get("/capability-signals/rules")
async def get_capability_signal_rules():
    return capability_signal_rules()


@router.post("/capability-signals/evaluate")
async def evaluate_capability_signals(event: CapabilitySignalEvent):
    return await evaluate_capability_signal_event(event)
