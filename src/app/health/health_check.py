from typing import Literal

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel

from app.container import get_container
from app.core.database.database import database_is_ready

router = APIRouter(prefix="/health", tags=["health"])

class HealthResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    
class LangChainHealthResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    chat_model: str | None = None
    embedding_dimensions: int | None = None
    model_response: str | None = None

@router.get("/live", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    return HealthResponse(status="ok")

@router.get(
    "/ready",
    response_model=HealthResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse}},
)
async def readiness(request: Request, response: Response) -> HealthResponse:
    container = get_container(request)
    if await database_is_ready(container.engine):
        return HealthResponse(status="ok")

    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(status="unavailable")

# @router.get(
#     "/ready/langchain",
#     response_model=LangChainHealthResponse,
#     responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": LangChainHealthResponse}},
# )
# async def langchain_readiness(request: Request, response: Response) -> LangChainHealthResponse:
#     smoke_check = get_container(request).langchain_smoke_check
    
#     if smoke_check is None:
#         response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
#         return LangChainHealthResponse(status="unavailable")

    
#     try:
#         result = await smoke_check()
#     except Exception:
#         response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
#         return LangChainHealthResponse(status="unavailable")

        
#     return LangChainHealthResponse(
#         status="ok",
#         chat_model=result.chat_model,
#         embedding_dimensions=result.embedding_dimensions,
#         model_response=result.model_response,
#     )
