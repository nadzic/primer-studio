from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.meta import router as meta_router
from app.api.routes.research import router as research_router

api_router = APIRouter()

api_router.include_router(health_router, tags=["health"])
api_router.include_router(meta_router, prefix="/meta", tags=["meta"])
api_router.include_router(research_router, tags=["research"])
