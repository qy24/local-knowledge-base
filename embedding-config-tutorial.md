# 嵌入模型配置教程（Embedding Configuration）

嵌入模型（Embedding）负责把文本变成向量，是检索质量的基石：**配置不当会导致"检索不到"或"分数无意义"**。本教程说明如何为本地知识库系统配置嵌入模型。

---

## 1. 配置位置

两处等价，改完**需重启服务**（前端改则实时生效并持久化）：

- 前端「系统设置」页面（推荐，可视化）
- 后端配置文件 `backend/.env`

## 2. 相关配置项

| 配置项 | 含义 | 示例 |
|---|---|---|
| `EMBEDDING_MODE` | 模式：`openai`（云端 OpenAI 兼容接口）\| `dummy`（离线占位，仅调试） | `openai` |
| `EMBEDDING_BASE_URL` | 嵌入服务地址（任意 OpenAI 兼容端点） | `https://api.openai.com/v1` |
| `EMBEDDING_API_KEY` | 平台密钥 | `sk-xxx` |
| `EMBEDDING_MODEL` | 模型名 | `text-embedding-3-small` |
| `EMBEDDING_DIM` | **向量维度，必须与模型一致** | 见下表 |
| `EMBEDDING_BATCH_SIZE` | 批量嵌入大小（可调小省内存） | `16` |

> `EMBEDDING_DIM` 不一致的后果：向量空间错位，检索结果完全不可用（尤其使用 Qdrant 时）。

## 3. 云端厂商配置示例

```ini
# 例 1：OpenAI
EMBEDDING_MODE=openai
EMBEDDING_BASE_URL=https://api.openai.com/v1
EMBEDDING_API_KEY=sk-xxx
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIM=1536

# 例 2：智谱 GLM
EMBEDDING_BASE_URL=https://open.bigmodel.cn/api/paas/v4
EMBEDDING_MODEL=embedding-3
EMBEDDING_DIM=1024

# 例 3：阿里云百炼
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_MODEL=text-embedding-v3
EMBEDDING_DIM=1024
```

常用模型维度参考：`text-embedding-3-small`=1536，`text-embedding-3-large`=3072，智谱 `embedding-3`=1024，阿里 `text-embedding-v3`=1024。**以各平台文档为准**。

## 4. 切换模型后必须"重解析"

更换嵌入模型（或首次从 `dummy` 切到真实模型）后，**已入库文档的向量是旧模型生成的，维度/语义空间与新的查询向量不匹配，检索会失效**。必须：

1. 「文档管理」→ 对每个文档点**重解析**（自动重新切分 + 向量化 + 图谱抽取）；
2. 等待状态变为「完成」。

## 5. 可选：本地 OpenAI 兼容服务（如 Ollama）

系统按标准 OpenAI 兼容协议调用嵌入接口，因此本地部署的 OpenAI 兼容服务（如 Ollama 的 `/v1/embeddings`）也可直接对接：

```ini
EMBEDDING_MODE=openai
EMBEDDING_BASE_URL=http://127.0.0.1:11434/v1
EMBEDDING_API_KEY=ollama          # 本地服务通常不校验密钥，占位即可
EMBEDDING_MODEL=qwen3-embedding:8b-q4_K_M
EMBEDDING_DIM=4096                # 按实际模型维度填写
```

注意：本地模型推理较慢（首次加载更慢），适合隐私敏感、文档量小的场景；常规使用推荐云端嵌入。

## 6. 常见问题

| 现象 | 处理 |
|---|---|
| 检索分数无意义 / 全库都命中 | `EMBEDDING_MODE=dummy` 是占位模式；配置真实模型后**重解析**所有文档 |
| 检索结果乱 / 完全不对 | `EMBEDDING_DIM` 与模型实际维度不一致，或切换模型后未重解析 |
| 接口返回 401 | `EMBEDDING_API_KEY` 错误或未填 |
| 请求超时 | 首次加载/网络慢：调大 `EMBEDDING_BATCH_SIZE` 为更小值（如 8），或检查网络 |
| 服务端报维度错误（Qdrant） | 重建 collection 或换用 `local` 向量库；确认 `EMBEDDING_DIM` |

## 7. 验证配置是否生效

1. 「检索调试台」提问一个知识库内的问题；
2. 观察返回分数：**相关文档分数明显高于无关文档**（如 0.8 vs 0.3）；
3. 分数区分度差 → 检查嵌入配置或数据质量（标题/段落/术语规范）。
