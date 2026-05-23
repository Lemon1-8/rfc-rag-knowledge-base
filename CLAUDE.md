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
cd backend && python -m scripts.run_pipeline --limit 50

# 只做索引（跳过爬取，使用已有 processed/*.md）
cd backend && python -m scripts.run_pipeline --skip-crawl

# 清空 Qdrant 后重建索引
curl -X DELETE http://localhost:6333/collections/rfc_chunks_small
curl -X DELETE http://localhost:6333/collections/rfc_chunks_big
cd backend && python -m scripts.run_pipeline --skip-crawl
```

后端端口当前使用 **8001**（8000 被僵尸 Python 进程占用，`--reload` 自动重载不可靠时需手动 `taskkill` 杀进程后重启）。

## 架构

### 检索策略：Small-to-Big 两层

- **小 chunk**（≤500 字符）→ `rfc_chunks_small` collection（1024 维向量）→ 精确语义匹配
- **大 chunk**（完整 h2 section）→ `rfc_chunks_big` collection（无向量，主键查询）→ 喂 LLM
- 检索后多一次主键查询映射（毫秒级）：`小 chunk 检索 → parent_chunk_id 去重 → big collection 取原文`

### 切片器四种内容类型

`backend/app/pipeline/chunker.py` 对 RFC 内容分四类处理：
- `TERM_DEF`：术语定义，完整保留不切割
- `CODE_BLOCK`：ABNF/代码块，完整保留
- `LIST`：列表结构，保持完整
- `NARRATIVE`：普通叙述，超过上限按 RecursiveCharacterTextSplitter 降级切

### 检索链路

`query → Embedding(TEI:8888) → Qdrant Dense Top-20 → 去重 parent → fetch big chunks → Reranker(TEI:8889) Top-5 → Prompt → DeepSeek SSE 流式`

### 多轮对话

- 对话和消息持久化在 SQLite（`data/conversations.db`），`backend/app/core/database.py`
- 新对话自动创建，标题取首条问题前 40 字
- 每次请求将历史消息 `[{role, content}]` 注入 Prompt 的"历史对话"区域
- `POST /api/chat` 接受可选 `conversation_id`，为空则自动建新对话

### 关键模块

| 模块 | 路径 | 职责 |
|---|---|---|
| 爬虫 | `backend/app/pipeline/crawler.py` | Datatracker API 获取列表，`rfc-editor.org/rfc/{id}.txt` 获取纯文本 |
| 清洗器 | `backend/app/pipeline/cleaner.py` | RFC 纯文本 → Markdown + 章节提取 |
| 切片器 | `backend/app/pipeline/chunker.py` | Small-to-Big 双层 + 内容类型分治 |
| 索引器 | `backend/app/pipeline/indexer.py` | 批量向量化 + 写入 Qdrant 双 collection |
| Embedding | `backend/app/core/embedding.py` | TEI HTTP 客户端 → localhost:8888 `/embed` |
| Reranker | `backend/app/core/reranker.py` | TEI HTTP 客户端 → localhost:8889 `/rerank` |
| LLM | `backend/app/core/llm.py` | LangChain ChatOpenAI + DeepSeek，SSE 流式 |
| 向量库 | `backend/app/core/vector_store.py` | Qdrant 1.18 `query_points` API |
| 数据库 | `backend/app/core/database.py` | SQLite，conversations + messages 表 |
| 混合检索 | `backend/app/retrieval/hybrid_search.py` | Dense + Reranker |
| RAG 链 | `backend/app/retrieval/rag_chain.py` | 检索→Prompt→LLM SSE 编排，支持 history 参数 |

### 前端状态管理

`useChat` hook 提升到 `App.tsx` 层（非 ChatWindow 内），保证切换 tab 时对话状态不丢失。ChatWindow 为受控组件，通过 props 接收 `messages`、`isLoading`、`conversationId`、`onSend`、`onClear`。

### API 路由

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/chat` | SSE 流式对话，`{"query","conversation_id?","top_k"}` |
| GET | `/api/search?q=&top_k=` | 检索调试 |
| GET | `/api/documents` | 文档列表（元数据聚合） |
| GET | `/api/documents/{id}` | 文档详情（所有 chunk 完整内容） |
| POST | `/api/documents/crawl` | 触发爬取 |
| DELETE | `/api/documents/{id}` | 删除文档 |
| GET | `/api/conversations` | 对话列表 |
| POST | `/api/conversations` | 创建对话 |
| GET | `/api/conversations/{id}` | 对话详情（含消息列表） |
| DELETE | `/api/conversations/{id}` | 删除对话 |

SSE 事件顺序：`sources → token* → conversation_id → done`，错误时发 `error`。

## 已知注意事项

- **`_parse_md_meta` URL 解析**：`indexer.py:96` 的 `line[6:]` 偏移量对应 Markdown `> 来源: https://...` 的 7 字符前缀（`>` + 空格 + `来` + `源` + `:` + 空格 = 6 索引才到 URL）。之前 `line[4:]` 导致 URL 残留 `: ` 前缀，已修复。重新跑管道后新数据正确，旧脏数据由前端 `cleanUrl()` 兜底。
- **Qdrant chunk_id 可能重复**：多次跑管道未清库会导致同 `chunk_id` 多次 upsert，前端用 `` `${chunk_id}_${index}` `` 做 React key 避免重复 key 警告。

## 配置

`backend/.env`（从 `.env.example` 复制），关键变量：
- `DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` / `DEEPSEEK_MODEL`
- `TEI_EMBEDDING_URL`（默认 `http://localhost:8888`）
- `TEI_RERANKER_URL`（默认 `http://localhost:8889`）
- `QDRANT_URL`（默认 `http://localhost:6333`）

使用 `pydantic-settings` 加载，配置定义在 `backend/app/config.py`。

## 外部依赖

- **TEI Embedding**：localhost:8888，BGE-M3，dim=1024
- **TEI Reranker**：localhost:8889，BGE-Reranker-v2-m3
- **Qdrant**：localhost:6333，Docker 启动
- **DeepSeek API**：`api.deepseek.com`，OpenAI 兼容接口

这些是已有基础设施，不需要在本项目中重建。

## 重要约束

- 不做容器化部署（无 Dockerfile、无 Docker Compose）
- 不做增量更新，全量管道一次性跑通
- 旧代码不保留、不参考
- Qdrant 客户端版本 1.18.x，使用 `query_points()` 而非已废弃的 `search()`
- `scroll()` 返回 `(points, next_offset)` 元组
