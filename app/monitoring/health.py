from fastapi import APIRouter

from app.config import settings
from app.kafka_client.producer import kafka_is_available
from app.services.temporal_release_service import check_temporal_health

router = APIRouter()


@router.get("/health")
async def health_check():
    return {
        "status": "healthy"
    }


@router.get("/kafka-health")
async def kafka_health():
    healthy = kafka_is_available()
    return {
        "status": "healthy" if healthy else "unhealthy",
        "bootstrap_servers": settings.KAFKA_BOOTSTRAP_SERVERS
    }


@router.get("/temporal-health")
async def temporal_workflow_health():
    return await check_temporal_health()
