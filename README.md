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
| 前端 | React + TypeScript + Vite |

### 检索架构：Small-to-Big 两层

```
query → Embedding → Qdrant Dense Top-20 → 去重 parent → 取 big chunk
→ Reranker Top-5 → Prompt → LLM 流式生成
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
cp .env.example backend/.env
# 编辑 backend/.env，填入 DEEPSEEK_API_KEY

# 3. 安装后端依赖
cd backend && pip install -r requirements.txt

# 4. 爬取 RFC 并入库
python -m scripts.run_pipeline --limit 50

# 5. 启动后端
uvicorn app.main:app --reload --port 8000

# 6. 启动前端（新终端）
cd frontend && npm install && npm run dev
```

浏览器打开 `http://localhost:5173` 即可使用聊天界面。

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/chat` | SSE 流式对话，`{"query":"...","top_k":5}` |
| GET | `/api/search?q=&top_k=` | 检索调试 |
| GET | `/api/documents` | 文档列表 |
| POST | `/api/documents/crawl` | 触发爬取 |
| DELETE | `/api/documents/{id}` | 删除文档 |
| GET | `/api/health` | 健康检查 |

SSE 事件顺序：`sources → token* → done`

## 项目结构

```
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口
│   │   ├── config.py            # pydantic-settings 配置
│   │   ├── api/                 # chat, search, documents 路由
│   │   ├── core/                # embedding, reranker, llm, vector_store
│   │   ├── pipeline/            # crawler, cleaner, chunker, indexer
│   │   ├── retrieval/           # hybrid_search, rag_chain
│   │   ├── schemas/             # Pydantic 模型
│   │   └── services/
│   ├── scripts/run_pipeline.py  # 一键全量管道
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── api/client.ts        # SSE 客户端
│       ├── hooks/useChat.ts     # 聊天状态管理
│       └── components/          # Chat, DocumentManager, Search
└── data/                        # 运行时数据（不入库）
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
