"""Embedding 抽象：openai（云端兼容，默认）| dummy（离线开发占位）。"""
from __future__ import annotations

import hashlib
import math
from abc import ABC, abstractmethod

import httpx

from ..config import Settings


class Embedder(ABC):
    dim: int

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class OpenAICompatEmbedder(Embedder):
    def __init__(self, settings: Settings):
        self.base_url = settings.embedding_base_url.rstrip("/")
        self.api_key = settings.embedding_api_key
        self.model = settings.embedding_model
        self.dim = settings.embedding_dim
        self._batch = settings.embedding_batch_size

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), self._batch):
            batch = texts[i:i + self._batch]
            resp = httpx.post(
                f"{self.base_url}/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "input": batch},
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()["data"]
            data.sort(key=lambda x: x["index"])
            out.extend(d["embedding"] for d in data)
        return out


class DummyEmbedder(Embedder):
    """离线占位：确定性哈希向量。仅用于无网络开发/测试，检索效果有限。"""

    def __init__(self, settings: Settings):
        self.dim = 256

    def embed(self, texts: list[str]) -> list[list[float]]:
        results = []
        for text in texts:
            vec = [0.0] * self.dim
            for i in range(len(text) - 1):
                gram = text[i:i + 2]
                h = int(hashlib.md5(gram.encode()).hexdigest()[:8], 16)
                idx = h % self.dim
                sign = 1.0 if (h >> 16) % 2 == 0 else -1.0
                vec[idx] += sign
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            results.append([v / norm for v in vec])
        return results


def get_embedder(settings: Settings, model_override: str = "") -> Embedder:
    if settings.embedding_mode == "dummy":
        return DummyEmbedder(settings)
    return OpenAICompatEmbedder(settings)
