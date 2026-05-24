"""
RAGAS 评估脚本：对 RAG 知识库进行自动化质量评估。

用法:
    cd backend && python -m eval.eval_ragas
    cd backend && python -m eval.eval_ragas --top-k 8
    cd backend && python -m eval.eval_ragas --questions custom.json
"""

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# 确保 backend/ 在 sys.path 中，使 app.* 导入可用
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@dataclass
class RagResult:
    question: str = ""
    answer: str = ""
    contexts: list[str] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)
    error: str | None = None
    duration_ms: float = 0.0


async def _collect_rag_response(query: str, top_k: int = 5) -> RagResult:
    """分两步获取完整 context 和 answer。

    1. 调用 hybrid_search() 直接获取完整 context
    2. 调用 rag_query() 消费 SSE 流，收集完整 answer
    """
    from app.retrieval.hybrid_search import hybrid_search
    from app.retrieval.rag_chain import rag_query

    contexts: list[str] = []
    sources: list[dict] = []
    error: str | None = None

    try:
        retrieval_results = await hybrid_search(query, top_k=top_k)
        contexts = [r["content"] for r in retrieval_results if r.get("content")]
        sources = retrieval_results
    except Exception as e:
        error = f"检索失败: {e}"

    full_answer = ""
    try:
        async for event in rag_query(query, top_k=top_k):
            for line in event.split("\n"):
                line = line.strip()
                if not line or not line.startswith("data: "):
                    continue
                try:
                    payload = json.loads(line[len("data: "):])
                except json.JSONDecodeError:
                    continue

                ev_type = payload.get("type")
                if ev_type == "token":
                    full_answer += payload.get("content", "")
                elif ev_type == "error":
                    msg = payload.get("message", "未知 LLM 错误")
                    error = f"{error}; LLM 流错误: {msg}" if error else f"LLM 流错误: {msg}"
    except Exception as e:
        msg = f"LLM 流异常: {e}"
        error = f"{error}; {msg}" if error else msg

    return RagResult(
        question=query,
        answer=full_answer,
        contexts=contexts,
        sources=sources,
        error=error,
    )


def _build_evaluator_llm():
    """为 RAGAS 构建评判用 LLM（temperature=0.0，确定性评估）。"""
    from langchain_openai import ChatOpenAI
    from ragas.llms import LangchainLLMWrapper
    from app.config import settings

    base_llm = ChatOpenAI(
        model=settings.deepseek_model,
        openai_api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        temperature=0.0,
        max_tokens=2048,
    )
    return LangchainLLMWrapper(base_llm)


def _build_tei_embeddings():
    """构建 TEI 本地 Embedding 适配器（供 AnswerRelevancy 指标使用）。"""
    from ragas.embeddings import BaseRagasEmbeddings
    from app.config import settings

    class TEIEmbeddings(BaseRagasEmbeddings):
        """通过 TEI /embed HTTP 端点获取向量的适配器。"""

        async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
            import httpx
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{settings.tei_embedding_url}/embed",
                    json={"inputs": texts, "truncate": True},
                )
                resp.raise_for_status()
                return resp.json()

        async def aembed_query(self, text: str) -> list[float]:
            results = await self.aembed_documents([text])
            return results[0]

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            import asyncio
            return asyncio.run(self.aembed_documents(texts))

        def embed_query(self, text: str) -> list[float]:
            import asyncio
            return asyncio.run(self.aembed_query(text))

    return TEIEmbeddings()


def _build_metrics(evaluator_llm, tei_embeddings=None):
    """构建 RAGAS 四项评估指标。"""
    from ragas.metrics import (
        Faithfulness,
        AnswerRelevancy,
        ContextRecall,
        ContextPrecision,
    )

    metrics = [
        Faithfulness(llm=evaluator_llm),
        AnswerRelevancy(llm=evaluator_llm, embeddings=tei_embeddings) if tei_embeddings
        else AnswerRelevancy(llm=evaluator_llm),
        ContextRecall(llm=evaluator_llm),
        ContextPrecision(llm=evaluator_llm),
    ]
    return metrics


def _build_dataset(questions_data: list[dict], results: list[RagResult]):
    """用问题和 RAG 结果构建 HuggingFace Dataset（ragas 0.2.x 格式）。"""
    from datasets import Dataset

    dataset_dict = {
        "question": [],
        "answer": [],
        "contexts": [],
        "ground_truth": [],
    }
    for item, rag_result in zip(questions_data, results):
        contexts = rag_result.contexts if rag_result.contexts else [""]
        answer = rag_result.answer if rag_result.answer else ""

        dataset_dict["question"].append(rag_result.question)
        dataset_dict["answer"].append(answer)
        dataset_dict["contexts"].append(contexts)
        dataset_dict["ground_truth"].append(item.get("ground_truth_answer", ""))

    return Dataset.from_dict(dataset_dict)


def _extract_scores(score_result) -> dict:
    """从 RAGAS 评估结果中提取汇总分数字典。"""
    metric_names = ["faithfulness", "answer_relevancy", "context_recall", "context_precision"]
    scores = {}

    try:
        df = score_result.to_pandas()
        for name in metric_names:
            if name in df.columns:
                col = df[name].dropna()
                scores[name] = float(col.mean()) if len(col) > 0 else float("nan")
            else:
                scores[name] = float("nan")
        return scores
    except Exception:
        pass

    if isinstance(score_result, dict):
        for name in metric_names:
            scores[name] = float(score_result.get(name, float("nan")))
        return scores

    for name in metric_names:
        scores[name] = float("nan")
    return scores


def _extract_per_question_scores(score_result, num_questions: int) -> list[dict]:
    """从 RAGAS 结果中提取每题分数。"""
    metric_names = ["faithfulness", "answer_relevancy", "context_recall", "context_precision"]
    per_question = [{} for _ in range(num_questions)]

    try:
        df = score_result.to_pandas()
        for name in metric_names:
            if name in df.columns:
                for i, val in enumerate(df[name]):
                    if i < num_questions:
                        per_question[i][name] = (
                            float(val) if val is not None and str(val) != "nan" else float("nan")
                        )
            else:
                for i in range(num_questions):
                    per_question[i][name] = float("nan")
    except Exception:
        for i in range(num_questions):
            for name in metric_names:
                per_question[i][name] = float("nan")

    return per_question


def _print_summary(aggregate_scores: dict, per_question: list[dict]):
    """打印汇总表和每题明细。"""
    print("\n" + "=" * 75)
    print("  RAGAS 评估结果")
    print("=" * 75)

    labels = {
        "faithfulness": "忠实度 (Faithfulness)",
        "answer_relevancy": "答案相关性 (Answer Relevancy)",
        "context_recall": "上下文召回率 (Context Recall)",
        "context_precision": "上下文精确率 (Context Precision)",
    }
    for key, label in labels.items():
        val = aggregate_scores.get(key, float("nan"))
        print(f"  {label:<36s}: {val:.4f}")

    print("-" * 75)

    if not per_question:
        return

    header = (
        f"  {'问题':<40s}"
        f" {'Faith':>7s}"
        f" {'Rel':>7s}"
        f" {'CRec':>7s}"
        f" {'CPre':>7s}"
    )
    print(f"\n{header}")
    print("-" * 75)
    for pq in per_question:
        q = pq["question"][:38]
        print(f"  {q:<40s} "
              f"{pq.get('faithfulness', float('nan')):7.3f} "
              f"{pq.get('answer_relevancy', float('nan')):7.3f} "
              f"{pq.get('context_recall', float('nan')):7.3f} "
              f"{pq.get('context_precision', float('nan')):7.3f}")

    print("-" * 75)
    for key in ["faithfulness", "answer_relevancy", "context_recall", "context_precision"]:
        vals = [pq[key] for pq in per_question
                if key in pq and not (isinstance(pq[key], float) and pq[key] != pq[key])]
        if vals:
            print(f"  平均 {key}: {sum(vals) / len(vals):.4f}")


async def run_evaluation(
    questions_file: str | Path | None = None,
    top_k: int = 5,
    save_results: bool = True,
    verbose: bool = True,
) -> dict:
    """执行完整 RAGAS 评估流水线。"""
    # ---- 加载问题 ----
    if questions_file is None:
        questions_file = Path(__file__).parent / "test_questions.json"

    with open(questions_file, "r", encoding="utf-8") as f:
        questions_data = json.load(f)

    if not questions_data:
        print("错误: 测试问题集为空")
        sys.exit(1)

    if verbose:
        print(f"加载了 {len(questions_data)} 条测试问题")
        print(f"top_k = {top_k}\n")

    # ---- 执行 RAG 查询 ----
    results: list[RagResult] = []
    for i, item in enumerate(questions_data):
        question = item["question"]
        if verbose:
            print(f"[{i + 1}/{len(questions_data)}] Q: {question[:70]}...")

        t0 = time.time()
        rag_result = await _collect_rag_response(question, top_k=top_k)
        rag_result.duration_ms = (time.time() - t0) * 1000

        if rag_result.error and verbose:
            print(f"  [ERROR] {rag_result.error}")

        if verbose:
            print(f"  Contexts: {len(rag_result.contexts)}, "
                  f"答案长度: {len(rag_result.answer)} 字符, "
                  f"耗时: {rag_result.duration_ms:.0f}ms")

        results.append(rag_result)

    # ---- 构建评估数据 ----
    if verbose:
        print("\n准备 LLM 评判器...")

    evaluator_llm = _build_evaluator_llm()
    tei_embeddings = _build_tei_embeddings()

    if verbose:
        print("构建 RAGAS 评估数据集...")

    eval_dataset = _build_dataset(questions_data, results)
    metrics = _build_metrics(evaluator_llm, tei_embeddings)

    if not metrics:
        print("错误: 没有可用的评估指标")
        sys.exit(1)

    if verbose:
        print(f"已加载 {len(metrics)} 项指标，开始 RAGAS 评估...\n")

    # ---- 执行评估 ----
    # RAGAS 内部使用 OpenAIEmbeddings（context_recall/context_precision 需要），
    # 设置环境变量让其走 DeepSeek 兼容 API
    from app.config import settings

    prev_openai_key = os.environ.get("OPENAI_API_KEY")
    prev_openai_base = os.environ.get("OPENAI_API_BASE")
    os.environ["OPENAI_API_KEY"] = settings.deepseek_api_key
    os.environ["OPENAI_API_BASE"] = settings.deepseek_base_url

    t0 = time.time()
    try:
        from ragas import evaluate as ragas_evaluate
        score_result = ragas_evaluate(eval_dataset, metrics=metrics)
    except Exception as e:
        print(f"评估执行失败: {e}")
        import traceback
        traceback.print_exc()
        partial = {
            "metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "model": "deepseek-chat",
                "top_k": top_k,
                "num_questions": len(questions_data),
                "error": str(e),
            },
            "aggregate_scores": {},
            "per_question": [
                {
                    "question": r.question,
                    "ground_truth_answer": q.get("ground_truth_answer", ""),
                    "answer": r.answer,
                    "contexts": r.contexts,
                    "num_contexts": len(r.contexts),
                    "num_answer_chars": len(r.answer),
                    "duration_ms": r.duration_ms,
                    "error": r.error,
                }
                for q, r in zip(questions_data, results)
            ],
        }
        return {"detailed": partial}

    finally:
        # 恢复原有环境变量
        if prev_openai_key is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = prev_openai_key
        if prev_openai_base is None:
            os.environ.pop("OPENAI_API_BASE", None)
        else:
            os.environ["OPENAI_API_BASE"] = prev_openai_base

    eval_duration = time.time() - t0

    # ---- 提取和格式化结果 ----
    aggregate_scores = _extract_scores(score_result)
    per_question_scores = _extract_per_question_scores(score_result, len(questions_data))

    per_question = []
    for item, rag_result, scores in zip(questions_data, results, per_question_scores):
        entry = {
            "question": rag_result.question,
            "ground_truth_answer": item.get("ground_truth_answer", ""),
            "answer": rag_result.answer,
            "contexts": rag_result.contexts,
            "num_contexts": len(rag_result.contexts),
            "num_answer_chars": len(rag_result.answer),
            "duration_ms": rag_result.duration_ms,
            "error": rag_result.error,
            "scores": scores,
        }
        entry.update(scores)
        per_question.append(entry)

    detailed = {
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": "deepseek-chat",
            "top_k": top_k,
            "num_questions": len(questions_data),
            "total_duration_seconds": round(eval_duration, 1),
        },
        "aggregate_scores": aggregate_scores,
        "per_question": per_question,
    }

    # ---- 输出 ----
    if verbose:
        _print_summary(aggregate_scores, per_question)

    # ---- 保存 ----
    if save_results:
        results_dir = Path(__file__).parent / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%dT%H%M%S")
        out_path = results_dir / f"eval_{timestamp}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(detailed, f, ensure_ascii=False, indent=2)
        if verbose:
            print(f"\n结果已保存到 {out_path}")

    return {"detailed": detailed}


def main():
    import argparse

    parser = argparse.ArgumentParser(description="RAGAS RAG 质量评估")
    parser.add_argument(
        "--questions", default=None,
        help="测试问题 JSON 文件路径（默认使用内置 test_questions.json）",
    )
    parser.add_argument(
        "--top-k", type=int, default=5,
        help="每条问题检索的文档数（默认 5）",
    )
    parser.add_argument(
        "--no-save", action="store_true",
        help="不保存结果 JSON 文件",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="静默模式，仅输出最终汇总",
    )
    args = parser.parse_args()

    asyncio.run(run_evaluation(
        questions_file=args.questions,
        top_k=args.top_k,
        save_results=not args.no_save,
        verbose=not args.quiet,
    ))


if __name__ == "__main__":
    main()
