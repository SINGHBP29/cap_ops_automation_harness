from fastapi import APIRouter
from fastapi import HTTPException

from app.models.temporal_release import TemporalPhaseSubmission
from app.models.temporal_release import TemporalRefreshSubmission
from app.models.temporal_release import TemporalRollbackSubmission
from app.services.incident_packet_service import build_incident_packet
from app.services.temporal_release_service import ensure_controlled_release_workflow
from app.services.temporal_release_service import get_controlled_release_workflow_state
from app.services.temporal_release_service import signal_temporal_refresh
from app.services.temporal_release_service import signal_temporal_release_phase
from app.services.temporal_release_service import signal_temporal_rollback
from app.services.traffic_router_service import validate_release_phase_transition

router = APIRouter()


@router.get("/temporal-release-status")
async def temporal_release_status(incident_id: str | None = None):
    try:
        if incident_id:
            return await get_controlled_release_workflow_state(incident_id)

        incident_packet = await build_incident_packet()
        await ensure_controlled_release_workflow(incident_packet)
        return await get_controlled_release_workflow_state(incident_packet["incident_id"])
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/temporal-release-refresh")
async def temporal_release_refresh(submission: TemporalRefreshSubmission):
    return await signal_temporal_refresh(submission.incident_id, submission.note)


@router.post("/temporal-release-phase")
async def temporal_release_phase(submission: TemporalPhaseSubmission):
    validation_error = await validate_release_phase_transition(submission.incident_id, submission.phase)
    if validation_error:
        raise HTTPException(status_code=400, detail=validation_error)
    return await signal_temporal_release_phase(
        incident_id=submission.incident_id,
        phase=submission.phase,
        note=submission.note,
    )


@router.post("/temporal-release-rollback")
async def temporal_release_rollback(submission: TemporalRollbackSubmission):
    return await signal_temporal_rollback(submission.incident_id, submission.reason)
