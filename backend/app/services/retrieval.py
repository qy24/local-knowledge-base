"""混合检索：向量 + 图谱，融合排序；强制 allowed_kb_ids 权限过滤。

权限模型：所有检索方法唯一接受 allowed_kb_ids 作为数据范围，
由服务端从 API 密钥解析注入，客户端无法扩大。
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..config import Settings
from ..models import Chunk, KnowledgeBase
from ..stores import get_graph_store, get_vector_store
from .embedding import get_embedder
from . import llm as llm_svc


def search_knowledge(
    db: Session,
    settings: Settings,
    query: str,
    allowed_kb_ids: list[int],
    top_k: int = 8,
    graph_depth: int = 1,
    enable_graph: bool = True,
) -> dict:
    top_k = max(1, min(top_k, 50))
    graph_depth = max(0, min(graph_depth, 3))
    allowed = list(dict.fromkeys(allowed_kb_ids))

    embedder = get_embedder(settings)
    vstore = get_vector_store(settings)
    gstore = get_graph_store(settings)

    # 1) 向量检索（服务端强制 kb 过滤）
    query_vec = embedder.embed([query])[0]
    hits = vstore.search(query_vec, allowed, top_k * 2)

    # 2) 图谱检索：查询实体 + 子图扩展
    graph: dict = {"entities": [], "relations": []}
    graph_chunk_ids: set[int] = set()
    verified_chunk_ids: set[int] = set()
    if enable_graph and allowed:
        seed_names: list[str] = []
        # 2a) 字符串命中实体名（无需 LLM，稳定兜底）
        for kb_id in allowed:
            entities, _ = gstore.list_entities(kb_id, limit=1000, offset=0)
            for e in entities:
                name = str(e.get("name", ""))
                if name and name in query:
                    seed_names.append(name)
        # 2b) LLM 提取查询实体（有配置时）
        llm = llm_svc.resolve_llm(settings)
        if llm.configured():
            try:
                seed_names.extend(llm_svc.query_entities(llm, query))
            except Exception:
                pass
        seed_names = list(dict.fromkeys(n for n in seed_names if n))
        if seed_names:
            entities, relations = gstore.subgraph(allowed, seed_names, graph_depth)
            graph = {"entities": entities, "relations": relations}
            for e in entities:
                if e.get("source_chunk_id"):
                    graph_chunk_ids.add(e["source_chunk_id"])
                    if e.get("verified"):
                        verified_chunk_ids.add(e["source_chunk_id"])
            for r in relations:
                if r.get("source_chunk_id"):
                    graph_chunk_ids.add(r["source_chunk_id"])
                    if r.get("verified"):
                        verified_chunk_ids.add(r["source_chunk_id"])

    # 3) 融合：图谱命中块优先（已确认实体的命中加权），其余按向量分数
    fused: list[dict] = []
    seen: set[int] = set()
    for cid in graph_chunk_ids:
        if cid in seen:
            continue
        seen.add(cid)
        chunk = db.get(Chunk, cid)
        if chunk is None or chunk.kb_id not in allowed:
            continue
        score = 1.1 if cid in verified_chunk_ids else 1.0
        fused.append({
            "chunk_id": chunk.id, "kb_id": chunk.kb_id, "doc_id": chunk.doc_id,
            "content": chunk.content, "metadata": chunk.meta,
            "score": score, "source": "graph",
        })
    for hit in hits:
        cid = hit["chunk_id"]
        if cid in seen:
            continue
        seen.add(cid)
        p = hit["payload"]
        chunk = db.get(Chunk, cid)
        fused.append({
            "chunk_id": cid, "kb_id": p.get("kb_id"), "doc_id": p.get("doc_id"),
            "content": chunk.content if chunk else "",
            "metadata": chunk.meta if chunk else {},
            "score": round(hit["score"], 4), "source": "vector",
        })

    # 4) 补充文档名（批量查询，供引用展示）
    doc_ids = list({c["doc_id"] for c in fused if c.get("doc_id")})
    doc_names: dict[int, str] = {}
    if doc_ids:
        from ..models import Document
        rows = db.query(Document).filter(Document.id.in_(doc_ids)).all()
        doc_names = {d.id: d.filename for d in rows}
    for c in fused:
        c["doc_name"] = doc_names.get(c.get("doc_id"), "")

    fused = fused[:top_k]
    kbs = db.query(KnowledgeBase).filter(KnowledgeBase.id.in_(allowed)).all()
    return {
        "query": query,
        "chunks": fused,
        "graph": graph,
        "permission_scope": {"kb_ids": allowed},
        "kb_names": {kb.id: kb.name for kb in kbs},
    }


def graph_query(db: Session, settings: Settings, allowed_kb_ids: list[int],
                entity: str, relation_types: list[str] | None = None,
                depth: int = 2) -> dict:
    gstore = get_graph_store(settings)
    entities, relations = gstore.subgraph(
        allowed_kb_ids, [entity], depth=depth, relation_types=relation_types,
    )
    return {"entities": entities, "relations": relations,
            "permission_scope": {"kb_ids": list(dict.fromkeys(allowed_kb_ids))}}
