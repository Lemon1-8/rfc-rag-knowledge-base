import { useState } from "react";
import { Search, ExternalLink, Clock } from "lucide-react";
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
    <div className="flex flex-col h-full">
      {/* 面板头部 */}
      <div className="flex items-center justify-between px-6 py-4 border-b-2 border-gray-100">
        <h2 className="text-base font-bold tracking-tight text-gray-900">
          检索调试
        </h2>
        <span className="text-sm text-gray-400">Dense + Reranker</span>
      </div>

      {/* 面板内容 */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-3xl">
          {/* 搜索栏 */}
          <div className="flex gap-2 mb-6">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              placeholder="搜索 RFC 文档..."
              className="flex-1 bg-gray-100 rounded-md px-4 py-3 text-sm
                         focus:bg-white focus:border-2 focus:border-blue-500 focus:outline-none
                         transition-all duration-200 placeholder:text-gray-400 text-gray-900"
              style={{ fontFamily: "inherit" }}
            />
            <button
              onClick={handleSearch}
              disabled={loading || !query.trim()}
              className="h-12 px-6 bg-blue-500 text-white text-sm font-medium rounded-md
                         hover:bg-blue-600 hover:scale-105 transition-all duration-200
                         disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:scale-100
                         flex items-center gap-1.5"
            >
              {loading ? (
                <>
                  <span className="animate-spin inline-block">⏳</span>
                  搜索中...
                </>
              ) : (
                <>
                  <Search size={16} />
                  搜索
                </>
              )}
            </button>
          </div>

          {/* 搜索元信息 */}
          {time > 0 && (
            <div className="flex items-center gap-4 text-sm text-gray-400 mb-5">
              <span>
                找到 <strong className="text-gray-700">{results.length}</strong>{" "}
                条结果
              </span>
              <span className="flex items-center gap-1">
                <Clock size={13} />
                {time}ms
              </span>
            </div>
          )}

          {/* 空状态 */}
          {searched && !loading && results.length === 0 && (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-4">
                <Search size={28} className="text-gray-300" />
              </div>
              <p className="text-gray-400 text-sm">无匹配结果</p>
            </div>
          )}

          {!searched && (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-4">
                <Search size={28} className="text-gray-300" />
              </div>
              <p className="text-gray-400 text-sm">输入关键词检索 RFC 文档</p>
            </div>
          )}

          {/* 搜索结果列表 */}
          <ul className="space-y-3">
            {results.map((r, i) => (
              <li
                key={i}
                className="bg-gray-50 rounded-lg p-5 transition-all duration-200 hover:scale-[1.005]"
              >
                <div className="flex items-center gap-3 mb-2">
                  <span className="text-xs font-bold text-blue-500 font-mono bg-blue-50 px-2 py-0.5 rounded-full">
                    {r.score.toFixed(3)}
                  </span>
                  <strong className="text-sm text-gray-900">{r.title}</strong>
                </div>
                <p className="text-xs text-gray-400 mb-2">{r.section_path}</p>
                <p className="text-sm text-gray-600 leading-relaxed mb-3">
                  {r.content_preview}
                </p>
                <div>
                  {r.url ? (
                    <a
                      href={r.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 text-xs font-medium text-blue-500
                                 hover:text-blue-600 transition-colors"
                    >
                      <ExternalLink size={12} />
                      查看原文
                    </a>
                  ) : (
                    <span className="text-xs text-gray-400">无原文链接</span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
