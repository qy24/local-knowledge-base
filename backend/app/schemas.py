"""Pydantic 请求/响应模型。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    username: str
    role: str

    model_config = {"from_attributes": True}


class KBIn(BaseModel):
    name: str
    description: str = ""
    chunk_size: int = Field(default=512, ge=64, le=4096)
    chunk_overlap: int = Field(default=64, ge=0, le=1024)
    graph_extraction_enabled: bool = True
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""


class KBOut(BaseModel):
    id: int
    name: str
    description: str
    chunk_size: int
    chunk_overlap: int
    graph_extraction_enabled: bool
    llm_base_url: str
    llm_model: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentOut(BaseModel):
    id: int
    kb_id: int
    filename: str
    file_size: int
    file_type: str
    status: str
    error_msg: str = ""
    page_count: int = 0
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ChunkOut(BaseModel):
    id: int
    kb_id: int
    doc_id: int
    seq: int
    content: str
    metadata: dict = Field(default_factory=dict, validation_alias="meta")
    embedding_status: str = "pending"

    model_config = {"from_attributes": True, "populate_by_name": True}


class ChunkUpdateIn(BaseModel):
    content: str


class KeyIn(BaseModel):
    name: str
    key_type: str = "search"  # search | ingest | full
    allowed_kb_ids: list[int] = Field(default_factory=list)
    expires_at: datetime | None = None


class KeyOut(BaseModel):
    id: int
    name: str
    key_type: str
    allowed_kb_ids: list[int]
    expires_at: datetime | None
    revoked: bool
    last_used_at: datetime | None
    created_at: datetime
    key: str | None = None  # 创建时返回明文一次

    model_config = {"from_attributes": True}


class SearchIn(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=8, ge=1, le=50)
    graph_depth: int = Field(default=1, ge=0, le=3)
    enable_graph: bool = True


class GraphQueryIn(BaseModel):
    entity: str
    relation_types: list[str] | None = None
    depth: int = Field(default=2, ge=1, le=5)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatIn(BaseModel):
    model: str | None = None
    messages: list[ChatMessage] = Field(min_length=1)
    temperature: float = 0.2
    top_k: int = Field(default=8, ge=1, le=50)
    graph_depth: int = Field(default=1, ge=0, le=3)


class EntityUpdateIn(BaseModel):
    name: str | None = None
    type: str | None = None
    properties: dict[str, Any] | None = None
    verified: bool | None = None


class RelationUpdateIn(BaseModel):
    relation_type: str | None = None
    properties: dict[str, Any] | None = None
    verified: bool | None = None


class EntityCreateIn(BaseModel):
    name: str
    type: str = "术语"
    properties: dict[str, Any] = Field(default_factory=dict)


class RelationCreateIn(BaseModel):
    source_entity_id: str
    target_entity_id: str
    relation_type: str
    properties: dict[str, Any] = Field(default_factory=dict)


class EntityMergeIn(BaseModel):
    source_id: str
    target_id: str


class SettingsIn(BaseModel):
    embedding_mode: str | None = None
    embedding_base_url: str | None = None
    embedding_api_key: str | None = None
    embedding_model: str | None = None
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    graph_extraction_enabled: bool | None = None


class SettingsOut(BaseModel):
    embedding_mode: str
    embedding_base_url: str
    embedding_model: str
    llm_base_url: str
    llm_model: str
    graph_extraction_enabled: bool
    # 密钥脱敏展示
    embedding_api_key_masked: str = ""
    llm_api_key_masked: str = ""
