"""存储工厂：根据配置选择向量库/图库后端。"""
from __future__ import annotations

from ..config import Settings
from .graph import GraphStore, LocalGraphStore, Neo4jGraphStore
from .vector import LocalVectorStore, QdrantVectorStore, VectorStore

_store_registry: dict[str, object] = {}


def get_vector_store(settings: Settings) -> VectorStore:
    key = f"vector:{settings.vector_backend}"
    if key not in _store_registry:
        if settings.vector_backend == "qdrant":
            _store_registry[key] = QdrantVectorStore(settings)
        else:
            _store_registry[key] = LocalVectorStore(settings)
    return _store_registry[key]  # type: ignore[return-value]


def get_graph_store(settings: Settings) -> GraphStore:
    key = f"graph:{settings.graph_backend}"
    if key not in _store_registry:
        if settings.graph_backend == "neo4j":
            _store_registry[key] = Neo4jGraphStore(settings)
        else:
            _store_registry[key] = LocalGraphStore(settings)
    return _store_registry[key]  # type: ignore[return-value]


def close_stores() -> None:
    for obj in _store_registry.values():
        try:
            obj.close()
        except Exception:
            pass
    _store_registry.clear()
