"""应用配置：从环境变量 / .env 读取。"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # 基础
    app_name: str = "本地知识库系统"
    debug: bool = True
    data_dir: str = "data"
    database_url: str = "sqlite:///./data/kb.db"
    secret_key: str = "change-me-to-a-long-random-string"
    token_expire_minutes: int = 720

    # 管理员初始账号
    admin_username: str = "admin"
    admin_password: str = "admin123"

    # Embedding：openai（云端兼容）| dummy（离线占位）
    embedding_mode: str = "openai"
    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536
    embedding_batch_size: int = 16

    # 云端大模型（OpenAI 兼容）
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"

    # 向量库：local | qdrant
    vector_backend: str = "local"
    qdrant_url: str = "http://localhost:6333"

    # 图数据库：local | neo4j
    graph_backend: str = "local"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "neo4j"

    # 流水线
    default_chunk_size: int = 512
    default_chunk_overlap: int = 64
    graph_extraction_enabled: bool = True
    graph_batch_chunks: int = 8

    # MCP
    mcp_enabled: bool = True

    @property
    def data_dir_path(self) -> Path:
        p = Path(self.data_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()
