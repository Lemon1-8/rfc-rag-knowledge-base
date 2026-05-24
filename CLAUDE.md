# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

个人学习用的 RFC 技术文档 RAG 知识库。混搭架构：自部署 Embedding/Reranker/向量库 + API 调用 LLM，Python + FastAPI 后端，React 前端。

## 启动命令

```bash
# Qdrant（Docker，仅数据库）
docker run -d -p 6333:6333 -v ./data/qdrant_storage:/qdrant/storage qdrant/qdrant

# 后端
cd backend && uvicorn app.main:app --reload --port 8001

# 前端
cd frontend && npm run dev

# 全量数据管道（爬取 → 清洗 → 切片 → 向量化 → 入库）
cd backend && python -m scripts.run_pipeline --limit 1000

# 只做索引（跳过爬取，使用已有 processed/*.md）
cd backend && python -m scripts.run_pipeline --skip-crawl

# 清空 Qdrant 后重建
curl -X DELETE http://localhost:6333/collections/rfc_chunks_small
curl -X DELETE http://localhost:6333/collections/rfc_chunks_big
cd backend && python -m scripts.run_pipeline --skip-crawl
# 管道跑完后重建 BM25 索引
curl -X POST http://localhost:8001/api/documents/rebuild-index

# 精确补爬（按 RFC 编号增量索引，不影响已有数据）
cd backend && python -m scripts.crawl_targeted --all-missing
cd backend && python -m scripts.crawl_targeted --rfcs 793 8446 6749

# RAGAS 质量评估
cd backend && pip install ragas datasets
cd backend && python -m eval.eval_ragas
cd backend && python -m eval.eval_ragas --top-k 8
```

后端端口固定使用 **8001**（8000 被僵尸 Python 进程占用）。`--reload` 热重载偶尔失效，代码未生效时需 `taskkill /F /IM python.exe` 强杀后重启。

## 架构

### 检索链路（Hybrid Search）

```
query → Dense(TEI:8888 Embed, Qdrant Top-30) ─┐
query → Sparse(本地 BM25, Top-30)            ─┤
                                              ├→ RRF 融合 → 去重 parent → fetch big chunks
                                              → Reranker(TEI:8889, Top-N) → 分数阈值过滤
                                              → Prompt + 对话历史 → DeepSeek SSE 流式
```

- **Dense**：BGE-M3 向量（1024 维）→ Qdrant 余弦相似度检索
- **Sparse**：BM25 Okapi 关键词检索（纯 Python 实现，`core/sparse_search.py`），补语义搜索的精确术语盲区
- **RRF 融合**（`k=60`）：基于排名融合两路结果，双路命中文档提权
- **Reranker**：BGE-Reranker-v2-m3 重排序，带 `score_threshold`（默认 0.15）过滤不相关文档
- **LLM**：DeepSeek（temperature=0.15, max_tokens=4096），低温度严格基于文档

BM25 索引在应用启动 `lifespan` 中自动构建，数据变更后调用 `POST /api/documents/rebuild-index` 重建。

### Small-to-Big 两层存储

- **小 chunk**（≤500 字符，50 字符重叠）→ `rfc_chunks_small` collection（1024 维向量）→ 精确检索
- **大 chunk**（完整 h2 section，最少 20 字符）→ `rfc_chunks_big` collection（无向量，主键查询）→ 喂 LLM
- 映射关系：多个小 chunk 通过 `parent_chunk_id` 指向同一个大 chunk

### 切片器四种内容类型

`backend/app/pipeline/chunker.py` 对 RFC 内容分四类处理：
- `TERM_DEF`：术语定义，完整保留不切割
- `CODE_BLOCK`：ABNF/代码块，完整保留
- `LIST`：列表结构，保持完整
- `NARRATIVE`：普通叙述，超过上限按 RecursiveCharacterTextSplitter 降级切

### 多轮对话

- 对话和消息持久化在 SQLite（`data/conversations.db`），`backend/app/core/database.py`
- 新对话自动创建，标题取首条问题前 40 字
- 每次请求将历史消息注入 Prompt 的"历史对话"区域
- `POST /api/chat` 接受可选 `conversation_id`，为空则自动建新对话

### 前端：Flat Design 浅色主题

- **技术**：React 19 + TypeScript + Vite + Tailwind CSS v4
- **图标**：lucide-react，**字体**：Outfit（Google Fonts，几何无衬线）
- **设计原则**：零阴影、纯色块分区、粗体排版、几何装饰、scale 交互动效
- **状态管理**：`useChat` hook 提升到 `App.tsx` 层，切换 tab 不丢失对话状态。ChatWindow 为受控组件
- **布局**：白色顶栏 + 灰色 100 侧边栏 + 白色主内容区，flexbox 非 fixed 定位

### 关键模块

| 模块 | 路径 | 职责 |
|---|---|---|
| 爬虫 | `backend/app/pipeline/crawler.py` | Datatracker API 获取列表，`rfc-editor.org/rfc/{id}.txt` 获取纯文本 |
| 清洗器 | `backend/app/pipeline/cleaner.py` | RFC 纯文本 → Markdown + 章节提取 |
| 切片器 | `backend/app/pipeline/chunker.py` | Small-to-Big 双层 + 内容类型分治 |
| 索引器 | `backend/app/pipeline/indexer.py` | 批量向量化 + 写入 Qdrant 双 collection |
| Embedding | `backend/app/core/embedding.py` | TEI HTTP 客户端 → localhost:8888 `/embed` |
| Reranker | `backend/app/core/reranker.py` | TEI HTTP 客户端 → localhost:8889 `/rerank`，支持 score_threshold 过滤 |
| LLM | `backend/app/core/llm.py` | LangChain ChatOpenAI + DeepSeek，SSE 流式 |
| 向量库 | `backend/app/core/vector_store.py` | Qdrant 1.18 `query_points` API |
| BM25 检索 | `backend/app/core/sparse_search.py` | 纯 Python BM25 Okapi 实现 + SparseRetriever |
| 数据库 | `backend/app/core/database.py` | SQLite，conversations + messages 表 |
| 混合检索 | `backend/app/retrieval/hybrid_search.py` | Dense + Sparse + RRF 融合 + Reranker 分数过滤 |
| RAG 链 | `backend/app/retrieval/rag_chain.py` | 检索→Prompt→LLM SSE 编排，支持 history 参数 |
| 评估 | `backend/eval/eval_ragas.py` | RAGAS 4 项指标 + TEI Embedding 适配器，结果存 `eval/results/` |
| 补爬 | `backend/scripts/crawl_targeted.py` | 按 RFC 编号精确爬取 + 临时目录增量索引 + BM25 重建 |

## API 路由

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/chat` | SSE 流式对话，`{"query","conversation_id?","top_k"}` |
| GET | `/api/search?q=&top_k=` | 检索调试 |
| GET | `/api/documents` | 文档列表（全量翻页聚合） |
| GET | `/api/documents/{id}` | 文档详情（所有 chunk 完整内容） |
| POST | `/api/documents/crawl` | 触发爬取 |
| DELETE | `/api/documents/{id}` | 删除文档并重建 BM25 索引 |
| POST | `/api/documents/rebuild-index` | 手动重建 BM25 稀疏索引 |
| GET | `/api/conversations` | 对话列表 |
| POST | `/api/conversations` | 创建对话 |
| GET | `/api/conversations/{id}` | 对话详情（含消息列表） |
| DELETE | `/api/conversations/{id}` | 删除对话 |

SSE 事件顺序：`sources → token* → conversation_id → done`，错误时发 `error`。

## RAGAS 评估

`backend/eval/eval_ragas.py` 分三步执行：

1. **检索获取**：直接调用 `hybrid_search(query)` 拿完整 context（不经过 SSE 截断），调用 `rag_query()` 收集 LLM 答案
2. **构建数据集**：`datasets.Dataset` 格式 `{question, answer, contexts, ground_truth}`
3. **RAGAS 评估**：`evaluate()` 计算 4 项指标

四个指标中，`faithfulness` / `context_recall` / `context_precision` 只需 LLM 评判，`answer_relevancy` 额外需要 Embedding 服务。项目中通过 `TEIEmbeddings`（继承 `BaseRagasEmbeddings`，调用 TEI `/embed` 端点）替代默认 OpenAI Embeddings，零成本完成所有指标测量。

评估结果 JSON 保存在 `backend/eval/results/`（已加入 `.gitignore`）。

## 配置

`backend/.env`（`pydantic-settings` 加载，定义在 `backend/app/config.py`）：

| 变量 | 说明 | 默认值 |
|---|---|---|
| `DEEPSEEK_API_KEY` | API 密钥 | — |
| `DEEPSEEK_BASE_URL` | API 地址 | `https://api.deepseek.com/v1` |
| `DEEPSEEK_MODEL` | 模型名 | `deepseek-chat` |
| `LLM_TEMPERATURE` | 生成温度 | `0.15` |
| `LLM_MAX_TOKENS` | 最大输出 token | `4096` |
| `RERANKER_SCORE_THRESHOLD` | Reranker 最低分数 | `0.15` |
| `DENSE_TOP` | Dense 检索数量 | `30` |
| `SPARSE_TOP` | BM25 检索数量 | `30` |
| `TEI_EMBEDDING_URL` | Embedding 服务 | `http://localhost:8888` |
| `TEI_RERANKER_URL` | Reranker 服务 | `http://localhost:8889` |
| `QDRANT_URL` | Qdrant 地址 | `http://localhost:6333` |

## 外部依赖（不在本项目内）

- **TEI Embedding**：localhost:8888，BGE-M3，dim=1024
- **TEI Reranker**：localhost:8889，BGE-Reranker-v2-m3
- **Qdrant**：localhost:6333，Docker 启动
- **DeepSeek API**：`api.deepseek.com`，OpenAI 兼容接口

## 重要约束

- 不做容器化部署（无 Dockerfile、无 Docker Compose）
- 不做增量更新，全量管道一次性跑通
- 旧代码不保留、不参考
- Qdrant 客户端版本 1.18.x，使用 `query_points()` 而非已废弃的 `search()`
- `scroll()` 返回 `(points, next_offset)` 元组，需要 while 循环翻页取全量
- Tailwind CSS v4 通过 `@import "tailwindcss"` 引入 CSS，`@tailwindcss/vite` 插件处理构建
- Prompt 模板严格要求基于文档、引用标注、参数准确、不编造信息
- RAGAS 依赖 `langchain-community`，新版（≥0.4）移除了 `chat_models.vertexai` 模块，如遇 `ModuleNotFoundError` 需在 `site-packages/langchain_community/chat_models/vertexai.py` 放置 shim 从 `langchain_google_vertexai` 导入 `ChatVertexAI`
