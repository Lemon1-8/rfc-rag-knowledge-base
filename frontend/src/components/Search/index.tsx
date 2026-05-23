import { useState } from "react";
import { searchDocuments } from "../../api/client";

export default function SearchPanel() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [time, setTime] = useState(0);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setSearched(true);
    try {
      const data = await searchDocuments(query);
      setResults(data.results);
      setTime(data.query_time_ms);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel">
      <div className="panel-header">
        <h3>检索调试</h3>
        <div className="panel-header-actions">
          <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
            Dense + Reranker
          </span>
        </div>
      </div>
      <div className="panel-body">
        <div className="search-form">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            placeholder="搜索 RFC 文档..."
          />
          <button onClick={handleSearch} disabled={loading}>
            {loading ? "搜索中..." : "搜索"}
          </button>
        </div>

        {time > 0 && (
          <p className="search-meta">
            找到 {results.length} 条结果 · 耗时 {time}ms
          </p>
        )}

        {searched && !loading && results.length === 0 && (
          <div className="empty-state">
            <div className="empty-icon">🔎</div>
            <p>无匹配结果</p>
          </div>
        )}

        {!searched && (
          <div className="empty-state">
            <div className="empty-icon">⌨️</div>
            <p>输入关键词检索 RFC 文档</p>
          </div>
        )}

        <ul className="search-results">
          {results.map((r, i) => (
            <li key={i} className="search-item">
              <div className="search-item-header">
                <span className="score">{r.score.toFixed(3)}</span>
                <strong>{r.title}</strong>
              </div>
              <div className="search-item-section">{r.section_path}</div>
              <p className="search-item-preview">{r.content_preview}</p>
              <div className="search-item-footer">
                {r.url ? (
                  <a href={r.url} target="_blank" rel="noopener noreferrer">
                    查看原文
                  </a>
                ) : (
                  <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
                    无原文链接
                  </span>
                )}
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
