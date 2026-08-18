"""云端大模型（OpenAI 兼容）客户端：图谱抽取 + 聚合生成。"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod

import httpx

from ..config import Settings

GRAPH_EXTRACT_SYSTEM = (
    "你是知识图谱抽取引擎。从给定的文本中抽取实体与关系。"
    "实体类型：人物/组织/产品/术语/事件/指标/地点。"
    '只输出 JSON：{"entities":[{"name":"..","type":".."}],'
    '"relations":[{"source":"..","target":"..","type":".."}]}。'
    "实体名要简洁规范，同名实体合并；relation 的 source/target 必须是已列出的实体名。"
    "如果文本没有实体，输出 {\"entities\":[],\"relations\":[]}。"
)

QUERY_ENTITY_SYSTEM = (
    "你是信息检索助手。从用户查询中识别可能指向知识库实体的关键名词（人名/组织/产品/术语/指标）。"
    '只输出 JSON：{"entities":["名称1","名称2"]}。没有则输出 {"entities":[]}。'
)


class LLMClient(ABC):
    @abstractmethod
    def chat(self, messages: list[dict], json_mode: bool = False,
             temperature: float = 0.2, max_tokens: int = 2048) -> str: ...

    def configured(self) -> bool:
        return True


class OpenAICompatLLM(LLMClient):
    def __init__(self, base_url: str, api_key: str, model: str, timeout: int = 180):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def configured(self) -> bool:
        return bool(self.api_key and self.model)

    def chat(self, messages: list[dict], json_mode: bool = False,
             temperature: float = 0.2, max_tokens: int = 2048) -> str:
        body: dict = {"model": self.model, "messages": messages,
                      "temperature": temperature, "max_tokens": max_tokens}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=body, timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


class DummyLLM(LLMClient):
    """离线占位：图谱抽取返回空结构，对话返回固定文本。仅开发/测试用。"""

    def __init__(self, settings: Settings | None = None):
        pass

    def configured(self) -> bool:
        return True

    def chat(self, messages: list[dict], json_mode: bool = False,
             temperature: float = 0.2, max_tokens: int = 2048) -> str:
        if json_mode:
            return '{"entities":[],"relations":[]}'
        return "（离线模式回答：未配置云端大模型）"


def resolve_llm(settings: Settings, kb=None) -> LLMClient:
    """按知识库覆盖 -> 全局配置 -> 离线占位 解析 LLM 客户端。"""
    if kb is not None and kb.llm_base_url and kb.llm_api_key and kb.llm_model:
        return OpenAICompatLLM(kb.llm_base_url, kb.llm_api_key, kb.llm_model)
    if settings.llm_api_key and settings.llm_base_url:
        return OpenAICompatLLM(settings.llm_base_url, settings.llm_api_key, settings.llm_model)
    return DummyLLM()


def extract_graph(llm: LLMClient, texts: list[str]) -> dict:
    """从若干切分块抽取实体/关系。"""
    prompt = "\n\n---\n\n".join(
        f"[片段 {i + 1}]\n{t[:1500]}" for i, t in enumerate(texts)
    )
    content = llm.chat(
        [{"role": "system", "content": GRAPH_EXTRACT_SYSTEM},
         {"role": "user", "content": prompt}],
        json_mode=True, max_tokens=4096,
    )
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"entities": [], "relations": []}


def query_entities(llm: LLMClient, query: str) -> list[str]:
    content = llm.chat(
        [{"role": "system", "content": QUERY_ENTITY_SYSTEM},
         {"role": "user", "content": query}],
        json_mode=True, max_tokens=512,
    )
    try:
        raw = json.loads(content).get("entities", [])
    except json.JSONDecodeError:
        return []
    out = []
    for item in raw:
        name = item if isinstance(item, str) else (item or {}).get("name", "")
        if name:
            out.append(str(name).strip())
    return [n for n in out if n]
