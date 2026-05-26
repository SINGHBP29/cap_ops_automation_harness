from fastapi import APIRouter

from app.models.ops_event import RawOpsEvent
from app.signal_detection.capture import OpsSignalCaptureService
from app.state.ops_ledger import ledger_snapshot

router = APIRouter()
service = OpsSignalCaptureService()


@router.get("/ops-events")
async def get_ops_events():
    return ledger_snapshot()


@router.get("/ops-ledger")
async def get_ops_ledger():
    return ledger_snapshot()


@router.post("/ops-events/ingest")
async def ingest_raw_ops_event(event: RawOpsEvent, derive_signals: bool = True):
    return await service.ingest_event(event, derive_signals=derive_signals)
