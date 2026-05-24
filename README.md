# RFC RAG 知识库

基于 **RAG（检索增强生成）** 的 RFC 技术文档知识库，支持语义检索与智能问答。个人学习项目。

## 技术栈

| 组件 | 技术 |
|---|---|
| 后端 | Python + FastAPI |
| LLM | DeepSeek（OpenAI 兼容，SSE 流式，temperature=0.15） |
| Embedding | BGE-M3（TEI 服务，1024 维） |
| Reranker | BGE-Reranker-v2-m3（TEI 服务） |
| 向量库 | Qdrant 1.18（Docker） |
| 对话持久化 | SQLite |
| 前端 | React 19 + TypeScript + Vite + Tailwind CSS v4 |
| 质量评估 | RAGAS（忠实度 / 相关性 / 召回率 / 精确率） |

## 检索架构

```
query ─┬→ Dense (BGE-M3 → Qdrant 余弦, Top-30) ─┐
       └→ Sparse (BM25 Okapi 关键词, Top-30)  ──┤
                                                  ├→ RRF 融合 (k=60) → 去重 parent
                                                  → 取 Big Chunk → Reranker (Top-N)
                                                  → 分数阈值过滤 → Prompt → DeepSeek SSE
```

**Hybrid Search = Dense + Sparse + RRF 融合。** Dense 做语义匹配，Sparse（BM25）补精确术语盲区，两路排名融合后经 Reranker 精排。

### Small-to-Big 双层存储

- **小 chunk**（≤500 字符，50 字符重叠）→ `rfc_chunks_small`（1024 维向量）→ 精确检索
- **大 chunk**（完整 h2 章节）→ `rfc_chunks_big`（仅主键查询）→ 喂 LLM
- 多对小 chunk 通过 `parent_chunk_id` 映射到同一大 chunk

切片器按内容类型分治：术语定义、代码块、列表保持完整，普通叙述超限降级切。

## 快速开始

### 前置依赖

以下服务需在本地运行（不在本项目内）：

- `localhost:8888` — TEI Embedding（BGE-M3）
- `localhost:8889` — TEI Reranker（BGE-Reranker-v2-m3）

### 启动

```bash
# 1. Qdrant
docker run -d -p 6333:6333 -v ./data/qdrant_storage:/qdrant/storage qdrant/qdrant

# 2. 环境变量
cp backend/.env.example backend/.env
# 编辑 backend/.env，填入 DEEPSEEK_API_KEY

# 3. 安装依赖
cd backend && pip install -r requirements.txt

# 4. 爬取 RFC 并入库（--limit 1000 全量，--limit 50 小规模测试）
python -m scripts.run_pipeline --limit 1000

# 5. 启动后端（固定端口 8001）
uvicorn app.main:app --reload --port 8001

# 6. 启动前端（新终端）
cd frontend && npm install && npm run dev
```

打开 `http://localhost:5173` 使用。

### 补爬与重建

```bash
# 清空 Qdrant 后重建
curl -X DELETE http://localhost:6333/collections/rfc_chunks_small
curl -X DELETE http://localhost:6333/collections/rfc_chunks_big
cd backend && python -m scripts.run_pipeline --skip-crawl

# 随时重建 BM25 索引（不重建向量）
curl -X POST http://localhost:8001/api/documents/rebuild-index
```

## 质量评估

基于 RAGAS 框架的自动化评估，10 条标准协议知识测试题。

```bash
cd backend && pip install ragas datasets
cd backend && python -m eval.eval_ragas
```

| 指标 | 分数 | 说明 |
|---|---|---|
| Faithfulness（忠实度） | 0.96 | 答案严格基于文档，不编造 |
| Answer Relevancy（相关性） | 0.78 | 回答扣题程度 |
| Context Recall（召回率） | 0.70 | 检索覆盖标准答案的比例 |
| Context Precision（精确率） | 0.74 | 检索结果中相关内容的占比 |

评估结果自动保存到 `backend/eval/results/`。

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/chat` | SSE 流式对话 `{"query","conversation_id?","top_k"}` |
| GET | `/api/search?q=&top_k=` | 检索调试，返回含相关度评分 |
| GET | `/api/documents` | 文档列表 |
| GET | `/api/documents/{id}` | 文档详情（所有 chunk 完整内容） |
| POST | `/api/documents/crawl` | 触发爬取 |
| DELETE | `/api/documents/{id}` | 删除文档并自动重建 BM25 |
| POST | `/api/documents/rebuild-index` | 手动重建 BM25 稀疏索引 |
| GET | `/api/conversations` | 对话列表 |
| POST | `/api/conversations` | 创建对话 |
| GET | `/api/conversations/{id}` | 对话详情（含历史消息） |
| DELETE | `/api/conversations/{id}` | 删除对话 |
| GET | `/api/health` | 健康检查 |

SSE 事件顺序：`sources → token* → conversation_id → done`

## 项目结构

```
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI 入口 + lifespan
│   │   ├── config.py               # pydantic-settings 配置
│   │   ├── api/                    # chat / search / documents / conversations
│   │   ├── core/                   # embedding / reranker / llm / vector_store / sparse_search / database
│   │   ├── pipeline/               # crawler / cleaner / chunker / indexer
│   │   ├── retrieval/              # hybrid_search (Dense+Sparse+RRF) / rag_chain (SSE)
│   │   └── schemas/                # Pydantic 模型
│   ├── eval/                       # RAGAS 评估
│   │   ├── test_questions.json     # 10 条测试题 + 标准答案
│   │   ├── eval_ragas.py           # 评估脚本（支持 TEI Embedding 适配器）
│   │   └── results/                # 评估结果 JSON
│   ├── scripts/
│   │   ├── run_pipeline.py         # 全量管道（爬取→清洗→切片→入库）
│   │   └── crawl_targeted.py       # 按 RFC 编号精确补爬 + 增量索引
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── App.tsx                 # 主布局 + 对话列表 + useChat 状态管理
│       ├── App.css                 # Flat Design 浅色主题
│       ├── api/client.ts           # 后端 API + SSE 客户端
│       ├── hooks/useChat.ts        # 多轮对话状态 Hook
│       └── components/             # Chat / DocumentManager / Search
└── data/                           # 运行时数据（不入 Git）
    ├── qdrant_storage/
    ├── conversations.db
    └── processed/                  # 清洗后的 Markdown
```

## 配置

`backend/.env`：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DEEPSEEK_API_KEY` | — | DeepSeek API 密钥 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com/v1` | API 地址 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 模型名 |
| `LLM_TEMPERATURE` | `0.15` | 生成温度 |
| `LLM_MAX_TOKENS` | `4096` | 最大输出 token |
| `RERANKER_SCORE_THRESHOLD` | `0.15` | Reranker 最低分数 |
| `TEI_EMBEDDING_URL` | `http://localhost:8888` | Embedding 服务 |
| `TEI_RERANKER_URL` | `http://localhost:8889` | Reranker 服务 |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant 地址 |
| `DENSE_TOP` | `30` | Dense 检索数量 |
| `SPARSE_TOP` | `30` | BM25 检索数量 |

## 约束与说明

- 不做容器化部署（无 Dockerfile / Docker Compose）
- 不做增量更新，管道全量一次性跑通
- 后端固定端口 **8001**（8000 被常驻进程占用）
- 旧代码不保留、不参考
- Prompt 模板严格要求基于文档、标注引用、不编造信息
