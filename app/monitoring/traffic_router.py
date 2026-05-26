from fastapi import APIRouter

from app.services.traffic_router_service import get_traffic_router_status
from app.services.traffic_router_service import sync_candidate_index

router = APIRouter()


@router.get("/traffic-router-status")
async def traffic_router_status():
    return await get_traffic_router_status(force_refresh=True)


@router.post("/shadow-index-sync")
async def shadow_index_sync(force: bool = True):
    return await sync_candidate_index(force=force)
