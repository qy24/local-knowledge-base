"""MCP Server：让支持 MCP 的 AI 客户端（Claude / Cursor / Dify 等）直接调用本地知识库。

- 传输：Streamable HTTP（挂载在 POST /mcp，SSE 响应）
- 鉴权：外层中间件校验 Bearer API 密钥，工具通过 Context.request.state.kb_scope 获取权限范围
- 权限：所有工具只在该密钥授权的知识库内检索（与 REST 接口同一套强制过滤）
- 工具：list_knowledge_bases / search_knowledge_base / get_graph_subgraph / list_documents
"""
from __future__ import annotations

import json

from mcp.server.fastmcp import Context, FastMCP

from .config import get_settings
from .database import SessionLocal
from .deps import KeyScope
from .models import Document, KnowledgeBase
from .services.retrieval import graph_query, search_knowledge

settings = get_settings()

mcp = FastMCP(
    "本地知识库",
    instructions=(
        "你是企业知识助手，使用本地知识库工具回答。"
        "回答前先调用 search_knowledge_base 获取相关知识与来源，"
        "严格基于检索结果回答并标注来源编号，检索不到时明确说明。"
    ),
    debug=False,
    log_level="ERROR",
)


def _scope(ctx: Context) -> KeyScope:
    """从 MCP 请求上下文取中间件注入的权限范围。"""
    rc = getattr(ctx, "request_context", None)
    request = getattr(rc, "request", None) if rc is not None else None
    state = getattr(request, "state", None)
    scope = getattr(state, "kb_scope", None) if state is not None else None
    if scope is None:
        raise PermissionError("缺少知识库访问权限：MCP 请求需携带有效 API 密钥")
    return scope


def _doc_names(doc_ids: list[int]) -> dict[int, str]:
    db = SessionLocal()
    try:
        rows = db.query(Document).filter(Document.id.in_(doc_ids)).all()
        return {d.id: d.filename for d in rows}
    finally:
        db.close()


@mcp.tool()
def list_knowledge_bases(ctx: Context) -> str:
    """列出当前密钥授权访问的知识库。"""
    scope = _scope(ctx)
    db = SessionLocal()
    try:
        kbs = db.query(KnowledgeBase).filter(KnowledgeBase.id.in_(scope.allowed_kb_ids)).all()
        return json.dumps(
            [{"kb_id": kb.id, "name": kb.name, "description": kb.description} for kb in kbs],
            ensure_ascii=False,
        )
    finally:
        db.close()


@mcp.tool()
def search_knowledge_base(ctx: Context, query: str, top_k: int = 8, graph_depth: int = 1) -> str:
    """在授权知识库内进行向量+图谱混合检索，返回带来源的知识片段与相关图谱。"""
    scope = _scope(ctx)
    db = SessionLocal()
    try:
        result = search_knowledge(
            db, settings, query, scope.allowed_kb_ids,
            top_k=max(1, min(top_k, 50)),
            graph_depth=max(0, min(graph_depth, 3)),
            enable_graph=True,
        )
    finally:
        db.close()

    entity_names = {e["id"]: e["name"] for e in result["graph"]["entities"]}
    relations = [
        {
            "source": entity_names.get(r["source_entity_id"], r.get("source_entity_id")),
            "target": entity_names.get(r["target_entity_id"], r.get("target_entity_id")),
            "type": r["relation_type"],
        }
        for r in result["graph"]["relations"]
    ]
    out = {
        "chunks": [
            {
                "content": c["content"],
                "doc_name": c.get("doc_name", ""),
                "page": c.get("metadata", {}).get("page", ""),
                "score": c["score"],
                "source": c["source"],
            }
            for c in result["chunks"]
        ],
        "graph": {
            "entities": [{"name": e["name"], "type": e["type"], "verified": e.get("verified", False)}
                         for e in result["graph"]["entities"]],
            "relations": relations,
        },
        "permission_scope": result["permission_scope"],
    }
    return json.dumps(out, ensure_ascii=False)


@mcp.tool()
def get_graph_subgraph(ctx: Context, entity: str, depth: int = 2) -> str:
    """按实体名在图谱中扩展 1~N 跳子图，返回相关实体与关系。"""
    scope = _scope(ctx)
    db = SessionLocal()
    try:
        result = graph_query(db, settings, scope.allowed_kb_ids,
                             entity=entity, depth=max(1, min(depth, 5)))
    finally:
        db.close()
    names = {e["id"]: e["name"] for e in result["entities"]}
    relations = [
        {
            "source": names.get(r["source_entity_id"], r.get("source_entity_id")),
            "target": names.get(r["target_entity_id"], r.get("target_entity_id")),
            "type": r["relation_type"],
        }
        for r in result["relations"]
    ]
    return json.dumps({
        "entities": [{"name": e["name"], "type": e["type"], "verified": e.get("verified", False)}
                     for e in result["entities"]],
        "relations": relations,
    }, ensure_ascii=False)


@mcp.tool()
def list_documents(ctx: Context) -> str:
    """列出当前密钥授权知识库内的文档（ID、文件名、处理状态）。"""
    scope = _scope(ctx)
    db = SessionLocal()
    try:
        docs = (db.query(Document)
                .filter(Document.kb_id.in_(scope.allowed_kb_ids))
                .order_by(Document.id.desc()).limit(500).all())
        return json.dumps(
            [{"doc_id": d.id, "kb_id": d.kb_id, "filename": d.filename, "status": d.status}
             for d in docs],
            ensure_ascii=False,
        )
    finally:
        db.close()


mcp_app = mcp.streamable_http_app()
# 供主应用 lifespan 管理任务组生命周期（manager.run() 上下文）
mcp_session_manager = getattr(mcp, "_session_manager", None)
