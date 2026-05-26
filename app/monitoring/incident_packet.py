from fastapi import APIRouter
from fastapi import HTTPException

from app.diagnosis.incident import IncidentPacketService

router = APIRouter()
service = IncidentPacketService()


@router.get("/incident-packet")
async def incident_packet():
    try:
        return await service.build_packet()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/incident-packet-llm")
async def incident_packet_llm():
    try:
        return await service.build_packet_llm()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
