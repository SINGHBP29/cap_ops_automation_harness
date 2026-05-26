from fastapi import APIRouter
from fastapi import HTTPException
from fastapi.responses import PlainTextResponse

from app.services.controlled_release_service import build_controlled_release_packet
from app.services.controlled_release_service import build_controlled_release_packet_llm
from app.services.incident_packet_service import build_incident_packet
from app.services.incident_packet_service import build_incident_packet_llm
from app.services.report_renderer import render_controlled_release_markdown
from app.services.report_renderer import render_incident_packet_markdown

router = APIRouter()


@router.get("/incident-report.md")
async def incident_report(use_llm: bool = False):
    try:
        packet = await (build_incident_packet_llm() if use_llm else build_incident_packet())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    markdown = render_incident_packet_markdown(packet)
    return PlainTextResponse(markdown, media_type="text/markdown")


@router.get("/controlled-release-report.md")
async def controlled_release_report(use_llm: bool = False):
    try:
        packet = await (
            build_controlled_release_packet_llm(record_audit=False)
            if use_llm
            else build_controlled_release_packet(record_audit=False)
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    markdown = render_controlled_release_markdown(packet)
    return PlainTextResponse(markdown, media_type="text/markdown")
