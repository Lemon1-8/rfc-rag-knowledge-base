"""
BM25 稀疏检索 —— 纯 Python 实现，补充语义搜索的关键词匹配盲区。
"""

import math
import re
from collections import Counter


def tokenize(text: str) -> list[str]:
    """英文技术文本分词：小写 → 提取字母数字 → 过滤单字符。"""
    text = text.lower()
    tokens = re.findall(r"[a-zA-Z0-9]{2,}", text)
    return tokens


class BM25:
    """BM25 评分器 —— Okapi BM25 实现。"""

    def __init__(self, corpus: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus = corpus
        self.n = len(corpus)
        self.doc_len = [len(tokenize(doc)) for doc in corpus]
        self.avgdl = sum(self.doc_len) / max(self.n, 1)

        # 文档频率
        df = Counter()
        for doc in corpus:
            unique_terms = set(tokenize(doc))
            for term in unique_terms:
                df[term] += 1

        # IDF
        self.idf = {
            term: math.log((self.n - freq + 0.5) / (freq + 0.5) + 1.0)
            for term, freq in df.items()
        }

    def score(self, query: str, doc_idx: int) -> float:
        """计算 query 对第 doc_idx 篇文档的 BM25 分数。"""
        query_tokens = tokenize(query)
        doc_tokens = tokenize(self.corpus[doc_idx])
        doc_counter = Counter(doc_tokens)
        doc_len = self.doc_len[doc_idx]

        total = 0.0
        for token in query_tokens:
            idf = self.idf.get(token)
            if idf is None:
                continue
            tf = doc_counter[token]
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / max(self.avgdl, 1))
            total += idf * numerator / denominator
        return total

    def search(self, query: str, top_k: int = 20) -> list[tuple[int, float]]:
        """搜索并返回 [(doc_idx, score), ...]，按分数降序。"""
        if self.n == 0:
            return []
        scores = []
        for i in range(self.n):
            s = self.score(query, i)
            if s > 0:
                scores.append((i, s))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


class SparseRetriever:
    """BM25 稀疏检索器，索引用小 chunk 的内容构建。"""

    def __init__(self):
        self.bm25: BM25 | None = None
        self.chunks: list[dict] = []  # [{chunk_id, parent_chunk_id, content}]
        self._built = False

    def build_index(self, vector_store) -> None:
        """从 Qdrant small collection 构建 BM25 索引。"""
        all_chunks = vector_store.scroll_all_small()
        if not all_chunks:
            self._built = True
            return

        self.chunks = all_chunks
        corpus = [c["content"] for c in all_chunks]
        self.bm25 = BM25(corpus)
        self._built = True

    def search(self, query: str, top_k: int = 20) -> list[tuple[str, float]]:
        """搜索，返回 [(parent_chunk_id, score), ...]。"""
        if not self._built or self.bm25 is None:
            return []
        results = self.bm25.search(query, top_k=top_k)
        return [(self.chunks[idx]["parent_chunk_id"], score) for idx, score in results]

    def rebuild(self, vector_store) -> None:
        """强制重建索引（管道重新入库后调用）。"""
        self.bm25 = None
        self.chunks = []
        self._built = False
        self.build_index(vector_store)


sparse_retriever = SparseRetriever()
