from fastapi import APIRouter
from fastapi import HTTPException

from app.release_control.plan import ControlledReleaseService

router = APIRouter()
service = ControlledReleaseService()


@router.get("/controlled-release-packet")
async def controlled_release_packet(record_audit: bool = False):
    try:
        return await service.build_packet(record_audit=record_audit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/controlled-release-packet-llm")
async def controlled_release_packet_llm(record_audit: bool = False):
    try:
        return await service.build_packet_llm(record_audit=record_audit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/controlled-release-audit-ledger")
async def controlled_release_audit_ledger():
    return service.get_audit_ledger()
