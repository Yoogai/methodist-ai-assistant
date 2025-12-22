from aiogram import Router
from .settings import router as settings_router
from .recognition import router as recognition_router
from .creative import router as creative_router
from .feedback import router as feedback_router
from .base import router as base_router
from .admin import router as admin_router

def get_user_router() -> Router:
    main_router = Router()
    # Порядок ВАЖЕН: сначала специфичные, потом общие
    main_router.include_router(settings_router)
    main_router.include_router(recognition_router)
    main_router.include_router(creative_router)
    main_router.include_router(feedback_router)
    main_router.include_router(base_router)
    return main_router

def get_admin_router() -> Router:
    return admin_router