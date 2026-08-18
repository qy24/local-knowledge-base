"""FastAPI 应用入口：初始化 DB/管理员/worker，托管前端静态文件，挂载 MCP。"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api.router import api_router
from .config import get_settings
from .database import SessionLocal, init_db
from .deps import resolve_key_scope
from .models import AppSetting, User
from .security import hash_password
from .stores import close_stores
from .workers import start_worker, stop_worker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("kb")

settings = get_settings()

# MCP session manager（在下方 if 块中赋值），lifespan 用它管理任务组
mcp_session_manager = None


def _apply_persisted_settings() -> None:
    db = SessionLocal()
    try:
        row = db.get(AppSetting, "runtime")
        if row and row.value:
            for k, v in row.value.items():
                if hasattr(settings, k):
                    setattr(settings, k, v)
    finally:
        db.close()


def _bootstrap_admin() -> None:
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            db.add(User(
                username=settings.admin_username,
                password_hash=hash_password(settings.admin_password),
                role="admin",
            ))
            db.commit()
            logger.info("已创建初始管理员: %s", settings.admin_username)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _apply_persisted_settings()
    _bootstrap_admin()
    start_worker()
    try:
        if mcp_session_manager is not None:
            async with mcp_session_manager.run():
                yield
        else:
            yield
    finally:
        stop_worker()
        close_stores()
    logger.info("知识库系统已停止")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="本地可视化知识库系统：多租户知识检索 API + 管理端",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发期放开；生产按需收紧
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def no_cache_html_middleware(request: Request, call_next):
    """HTML 响应禁用缓存，保证前端升级后刷新即可生效（JS/CSS 为哈希文件名，可正常缓存）。"""
    response = await call_next(request)
    if request.url.path in ("/", "/index.html") or request.url.path.endswith(".html"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.middleware("http")
async def spa_fallback_middleware(request: Request, call_next):
    """SPA 回退：前端路由（如 /keys、/documents?kb=1）直接刷新/直达时，
    静态服务找不到对应文件会 404，这里回退返回 index.html 交给前端路由接管。
    API(/api)、MCP(/mcp) 与带扩展名的静态资源 404 保持原样。"""
    response = await call_next(request)
    if response.status_code == 404 and request.method in ("GET", "HEAD"):
        path = request.url.path
        if (not path.startswith(("/api", "/mcp"))
                and not Path(path).suffix):  # 无文件扩展名 → 视为前端路由
            index = _dist / "index.html"
            if index.exists():
                return FileResponse(index, media_type="text/html",
                                    headers={"Cache-Control": "no-cache"})
    return response

app.include_router(api_router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.app_name}


# MCP Server（Streamable HTTP，密钥鉴权）——必须先于 "/" 静态挂载注册
if settings.mcp_enabled:
    from .mcp_server import mcp_app, mcp_session_manager as _mcp_sm  # noqa: E402

    mcp_session_manager = _mcp_sm

    @app.middleware("http")
    async def mcp_auth_middleware(request: Request, call_next):
        if request.url.path.startswith("/mcp"):
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return JSONResponse(status_code=401, content={"error": "缺少 API 密钥"})
            db = SessionLocal()
            try:
                scope = resolve_key_scope(db, auth_header[7:])
            finally:
                db.close()
            if scope is None:
                return JSONResponse(status_code=401, content={"error": "API 密钥无效、已吊销或已过期"})
            request.state.kb_scope = scope
        return await call_next(request)

    # FastMCP 的 streamable_http_app 自带 /mcp 路由，直接注册（不可再 mount 一层）
    for _route in mcp_app.routes:
        app.router.routes.append(_route)
    logger.info("已挂载 MCP Server: POST /mcp（Streamable HTTP）")

# 托管前端构建产物（存在时）——最后注册，兜底所有未匹配路径
_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="frontend")
    logger.info("已托管前端: %s", _dist)
