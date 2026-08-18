"""API 路由包。"""
from fastapi import APIRouter

from . import admin, auth, knowledge

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/admin", tags=["鉴权"])
api_router.include_router(admin.router, prefix="/admin", tags=["管理"])
api_router.include_router(knowledge.router, prefix="/v1", tags=["知识检索"])
