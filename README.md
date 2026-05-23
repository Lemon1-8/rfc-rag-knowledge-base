# RFC RAG 知识库

基于 **RAG（检索增强生成）** 的个人学习项目，对 RFC 技术文档进行语义检索和智能问答。

### 技术栈

| 组件 | 技术 |
|---|---|
| 后端框架 | Python + FastAPI |
| LLM | DeepSeek（OpenAI 兼容接口，SSE 流式） |
| Embedding | BGE-M3（TEI 服务，1024 维） |
| Reranker | BGE-Reranker-v2-m3（TEI 服务） |
| 向量库 | Qdrant（Docker） |
| 编排框架 | LangChain（ChatOpenAI + LCEL） |
| 持久化 | SQLite（对话历史） |
| 前端 | React 19 + TypeScript + Vite |

### 功能特性

- **RAG 问答**：Small-to-Big 双层检索 + Dense + Reranker，流式 SSE 输出
- **多轮对话**：对话历史持久化，支持切换、删除、上下文感知
- **文档管理**：卡片式浏览、全文查看、删除
- **检索调试**：原始检索结果查看，含相关度评分
- **SaaS 风格 UI**：深色主题，对话侧边栏，Toast 通知，加载骨架屏

### 检索架构：Small-to-Big 两层

```
query → Embedding → Qdrant Dense Top-20 → 去重 parent → 取 big chunk
→ Reranker Top-5 → Prompt + 对话历史 → LLM 流式生成
```

- **小 chunk**（≤500 字符）：带 1024 维向量，做精确语义匹配
- **大 chunk**（完整章节原文）：命中后完整喂给 LLM，保证上下文不截断

切片器按 RFC 内容类型分治：术语定义、代码块、列表保持完整不切，普通叙述超限降级切。

### 已有依赖

以下服务需要在本地运行（不在本项目内）：

- `localhost:8888` — TEI Embedding（BGE-M3）
- `localhost:8889` — TEI Reranker（BGE-Reranker-v2-m3）

## 快速开始

```bash
# 1. 启动 Qdrant
docker run -d -p 6333:6333 -v ./data/qdrant_storage:/qdrant/storage qdrant/qdrant

# 2. 配置 API Key
cp backend/.env.example backend/.env
# 编辑 backend/.env，填入 DEEPSEEK_API_KEY

# 3. 安装后端依赖
cd backend && pip install -r requirements.txt

# 4. 爬取 RFC 并入库
python -m scripts.run_pipeline --limit 50

# 5. 启动后端
uvicorn app.main:app --reload --port 8001

# 6. 启动前端（新终端）
cd frontend && npm install && npm run dev
```

浏览器打开 `http://localhost:5173` 即可使用。

### 重建索引

```bash
# 清空 Qdrant 后重建（使用已有 processed/*.md）
curl -X DELETE http://localhost:6333/collections/rfc_chunks_small
curl -X DELETE http://localhost:6333/collections/rfc_chunks_big
cd backend && python -m scripts.run_pipeline --skip-crawl
```

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/chat` | SSE 流式对话，`{"query","conversation_id?","top_k"}` |
| GET | `/api/search?q=&top_k=` | 检索调试，返回结果含 score |
| GET | `/api/documents` | 文档列表 |
| GET | `/api/documents/{id}` | 文档详情，返回所有章节完整内容 |
| POST | `/api/documents/crawl` | 触发爬取 |
| DELETE | `/api/documents/{id}` | 删除文档及其所有 chunk |
| GET | `/api/conversations` | 对话列表 |
| POST | `/api/conversations` | 创建新对话 |
| GET | `/api/conversations/{id}` | 对话详情（含历史消息） |
| DELETE | `/api/conversations/{id}` | 删除对话 |
| GET | `/api/health` | 健康检查 |

SSE 事件顺序：`sources → token* → conversation_id → done`

## 项目结构

```
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口
│   │   ├── config.py            # pydantic-settings 配置
│   │   ├── api/                 # chat, search, documents, conversations 路由
│   │   ├── core/                # embedding, reranker, llm, vector_store, database
│   │   ├── pipeline/            # crawler, cleaner, chunker, indexer
│   │   ├── retrieval/           # hybrid_search, rag_chain
│   │   └── schemas/             # Pydantic 模型
│   ├── scripts/run_pipeline.py  # 一键全量管道
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── App.tsx              # 主布局 + 对话列表 + useChat 状态管理
│       ├── App.css              # SaaS 风格全局样式
│       ├── api/client.ts        # 后端 API + SSE 客户端
│       ├── hooks/useChat.ts     # 多轮对话状态 Hook
│       └── components/          # Chat, DocumentManager, Search
└── data/                        # 运行时数据（不入库）
    ├── qdrant_storage/
    ├── conversations.db         # 对话 SQLite
    └── processed/               # 清洗后的 Markdown
```

## 配置

`backend/.env` 关键变量：

| 变量 | 说明 | 默认值 |
|---|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | — |
| `DEEPSEEK_BASE_URL` | API 地址 | `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | 模型名 | `deepseek-chat` |
| `TEI_EMBEDDING_URL` | Embedding 服务 | `http://localhost:8888` |
| `TEI_RERANKER_URL` | Reranker 服务 | `http://localhost:8889` |
| `QDRANT_URL` | Qdrant 地址 | `http://localhost:6333` |
