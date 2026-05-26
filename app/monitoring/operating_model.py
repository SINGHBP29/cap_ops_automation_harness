from fastapi import APIRouter

from app.operating_model.service import AISearchOpsHarnessService

router = APIRouter()
service = AISearchOpsHarnessService()


@router.get("/operating-model")
async def operating_model(query: str | None = None):
    return service.describe_operating_model(operator_query=query)
