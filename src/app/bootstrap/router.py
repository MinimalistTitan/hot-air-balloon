from fastapi import APIRouter

from app.modules.assistant.presentation.router import router as assistant_router
from app.modules.documents.presentation.router import router as documents_router
from app.modules.user.presentation.router import router as users_router
from app.modules.operations.presentation.router import router as operations_router
from app.health.health_check import router as health_router

def create_api_router() -> APIRouter:
    router = APIRouter()
    router.include_router(users_router)
    router.include_router(documents_router)
    router.include_router(assistant_router)
    router.include_router(operations_router)
    router.include_router(health_router)
    return router
