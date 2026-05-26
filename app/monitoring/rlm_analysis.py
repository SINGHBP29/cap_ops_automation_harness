from __future__ import annotations

from fastapi import APIRouter
from fastapi import HTTPException

from app.services.rlm_incident_orchestrator import build_rlm_incident_analysis

router = APIRouter()


@router.get("/rlm-incident-analysis")
async def rlm_incident_analysis():
    try:
        return await build_rlm_incident_analysis(use_llm=False)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/rlm-incident-analysis-llm")
async def rlm_incident_analysis_llm():
    try:
        return await build_rlm_incident_analysis(use_llm=True)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
