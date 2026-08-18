"""向量存储抽象：local（开发/单机回退）| qdrant（生产）。

检索方法统一接收 allowed_kb_ids —— 这是多租户权限过滤的强制入口，
任何调用方都无法绕过（服务端唯一拼过滤条件的位置）。
"""
from __future__ import annotations

import json
import threading
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np

from ..config import Settings


class VectorStore(ABC):
    @abstractmethod
    def upsert(self, kb_id: int, doc_id: int, chunk_id: int, seq: int,
               vector: list[float], doc_name: str, page: str | int) -> None: ...

    @abstractmethod
    def delete_by_doc(self, doc_id: int) -> None: ...

    @abstractmethod
    def delete_by_kb(self, kb_id: int) -> None: ...

    @abstractmethod
    def search(self, vector: list[float], allowed_kb_ids: list[int],
               top_k: int, threshold: float | None = None) -> list[dict]: ...

    @abstractmethod
    def count(self) -> int: ...

    @abstractmethod
    def close(self) -> None: ...


class LocalVectorStore(VectorStore):
    """内存 numpy 实现 + JSON/npz 持久化。适合单机中小规模（<5 万向量）。"""

    def __init__(self, settings: Settings):
        self._dir = settings.data_dir_path / "vectors"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._vectors: dict[str, np.ndarray] = {}
        self._payloads: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        vec_path = self._dir / "vectors.npz"
        pay_path = self._dir / "payloads.json"
        if vec_path.exists() and pay_path.exists():
            data = np.load(vec_path, allow_pickle=True)
            for key in data.files:
                self._vectors[str(key)] = data[key]
            with open(pay_path, "r", encoding="utf-8") as f:
                self._payloads = {k: v for k, v in json.load(f).items()}

    def _save(self) -> None:
        with self._lock:
            if not self._vectors:
                return
            np.savez(self._dir / "vectors.npz", **self._vectors)
            with open(self._dir / "payloads.json", "w", encoding="utf-8") as f:
                json.dump(self._payloads, f, ensure_ascii=False)

    def upsert(self, kb_id: int, doc_id: int, chunk_id: int, seq: int,
               vector: list[float], doc_name: str, page: str | int) -> None:
        key = str(chunk_id)
        with self._lock:
            self._vectors[key] = np.asarray(vector, dtype=np.float32)
            self._payloads[key] = {
                "kb_id": kb_id, "doc_id": doc_id, "chunk_id": chunk_id,
                "seq": seq, "doc_name": doc_name, "page": page,
            }
        self._save()

    def delete_by_doc(self, doc_id: int) -> None:
        with self._lock:
            dead = [k for k, p in self._payloads.items() if p["doc_id"] == doc_id]
            for k in dead:
                self._vectors.pop(k, None)
                self._payloads.pop(k, None)
        self._save()

    def delete_by_kb(self, kb_id: int) -> None:
        with self._lock:
            dead = [k for k, p in self._payloads.items() if p["kb_id"] == kb_id]
            for k in dead:
                self._vectors.pop(k, None)
                self._payloads.pop(k, None)
        self._save()

    def search(self, vector: list[float], allowed_kb_ids: list[int],
               top_k: int, threshold: float | None = None) -> list[dict]:
        q = np.asarray(vector, dtype=np.float32)
        qn = np.linalg.norm(q)
        if qn == 0:
            return []
        q = q / qn
        allowed = set(allowed_kb_ids)
        rows: list[tuple[float, str]] = []
        with self._lock:
            for key, v in self._vectors.items():
                payload = self._payloads[key]
                if payload["kb_id"] not in allowed:
                    continue
                norm = np.linalg.norm(v)
                if norm == 0:
                    continue
                score = float(np.dot(v, q) / norm)
                if threshold is None or score >= threshold:
                    rows.append((score, key))
        rows.sort(key=lambda x: x[0], reverse=True)
        return [
            {"chunk_id": int(k), "score": s, "payload": self._payloads[k]}
            for s, k in rows[:top_k]
        ]

    def count(self) -> int:
        with self._lock:
            return len(self._vectors)

    def close(self) -> None:
        self._save()


class QdrantVectorStore(VectorStore):
    """生产实现：Qdrant 单 collection + kb_id payload 过滤。"""

    def __init__(self, settings: Settings):
        from qdrant_client import QdrantClient
        from qdrant_client.http import models as qm

        self._client = QdrantClient(url=settings.qdrant_url)
        self._dim = settings.embedding_dim
        self._qm = qm
        exists = self._client.collection_exists("kb_chunks")
        if not exists:
            self._client.create_collection(
                collection_name="kb_chunks",
                vectors_config=qm.VectorParams(size=self._dim, distance=qm.Distance.COSINE),
            )

    def upsert(self, kb_id: int, doc_id: int, chunk_id: int, seq: int,
               vector: list[float], doc_name: str, page: str | int) -> None:
        self._client.upsert(
            collection_name="kb_chunks",
            points=[self._qm.PointStruct(
                id=chunk_id,
                vector=vector,
                payload={"kb_id": kb_id, "doc_id": doc_id, "chunk_id": chunk_id,
                         "seq": seq, "doc_name": doc_name, "page": page},
            )],
        )

    def delete_by_doc(self, doc_id: int) -> None:
        self._client.delete(
            collection_name="kb_chunks",
            points_selector=self._qm.FilterSelector(
                filter=self._qm.Filter(must=[
                    self._qm.FieldCondition(key="doc_id", match=self._qm.MatchValue(value=doc_id))
                ])
            ),
        )

    def delete_by_kb(self, kb_id: int) -> None:
        self._client.delete(
            collection_name="kb_chunks",
            points_selector=self._qm.FilterSelector(
                filter=self._qm.Filter(must=[
                    self._qm.FieldCondition(key="kb_id", match=self._qm.MatchValue(value=kb_id))
                ])
            ),
        )

    def search(self, vector: list[float], allowed_kb_ids: list[int],
               top_k: int, threshold: float | None = None) -> list[dict]:
        filt = self._qm.Filter(must=[
            self._qm.FieldCondition(key="kb_id", match=self._qm.MatchAny(any=allowed_kb_ids))
        ]) if allowed_kb_ids else None
        hits = self._client.search(
            collection_name="kb_chunks", query_vector=vector, query_filter=filt,
            limit=top_k, score_threshold=threshold,
        )
        return [
            {"chunk_id": h.id, "score": h.score, "payload": h.payload}
            for h in hits
        ]

    def count(self) -> int:
        return self._client.count(collection_name="kb_chunks").count

    def close(self) -> None:
        self._client.close()
