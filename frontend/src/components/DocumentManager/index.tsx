import { useState, useEffect } from "react";
import { RefreshCw, FileText, X, ExternalLink } from "lucide-react";
import {
  fetchDocuments,
  fetchDocumentContent,
  deleteDocument,
  type DocumentDetail,
} from "../../api/client";

/** 清理数据库中残留的脏 URL（如 ": https://..."） */
function cleanUrl(url: string): string {
  return url.replace(/^[:\s]+/, "").trim();
}

export default function DocumentManager() {
  const [docs, setDocs] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [viewing, setViewing] = useState<DocumentDetail | null>(null);
  const [viewLoading, setViewLoading] = useState(false);
  const [toast, setToast] = useState<{
    type: "success" | "error";
    msg: string;
  } | null>(null);

  const showToast = (type: "success" | "error", msg: string) => {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 3000);
  };

  const loadDocs = async () => {
    setLoading(true);
    try {
      const data = await fetchDocuments();
      setDocs(data);
    } catch {
      showToast("error", "加载文档列表失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDocs();
  }, []);

  const handleView = async (id: string) => {
    setViewLoading(true);
    try {
      const detail = await fetchDocumentContent(id);
      setViewing(detail);
    } catch {
      showToast("error", "加载文档内容失败");
    } finally {
      setViewLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("确定删除此文档？")) return;
    try {
      await deleteDocument(id);
      setDocs((prev) => prev.filter((d) => d.id !== id));
      showToast("success", "文档已删除");
    } catch {
      showToast("error", "删除失败");
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* 面板头部 */}
      <div className="flex items-center justify-between px-6 py-4 border-b-2 border-gray-100">
        <h2 className="text-base font-bold tracking-tight text-gray-900">
          文档管理
        </h2>
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-400">{docs.length} 个文档</span>
          <button
            onClick={loadDocs}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-500
                       rounded-md hover:text-gray-700 hover:bg-gray-100 transition-all duration-200
                       disabled:opacity-50"
          >
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
            刷新
          </button>
        </div>
      </div>

      {/* 面板内容 */}
      <div className="flex-1 overflow-y-auto p-6">
        {/* 骨架屏 */}
        {loading && (
          <div className="grid grid-cols-[repeat(auto-fill,minmax(320px,1fr))] gap-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="bg-gray-100 rounded-lg h-36 animate-pulse" />
            ))}
          </div>
        )}

        {/* 空状态 */}
        {!loading && docs.length === 0 && (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-4">
              <FileText size={28} className="text-gray-300" />
            </div>
            <p className="text-gray-400 text-sm">暂无文档，请先运行数据管道</p>
          </div>
        )}

        {/* 文档卡片网格 */}
        {!loading && docs.length > 0 && (
          <div className="grid grid-cols-[repeat(auto-fill,minmax(320px,1fr))] gap-4">
            {docs.map((doc) => (
              <div
                key={doc.id}
                className="group bg-gray-50 rounded-lg p-5 transition-all duration-200 hover:scale-[1.01]"
              >
                <div className="w-10 h-1 bg-blue-500 rounded-full mb-3" />
                <h3 className="font-semibold text-gray-900 mb-2 line-clamp-2 text-sm leading-snug">
                  {doc.title}
                </h3>
                <div className="flex items-center gap-3 text-xs mb-4">
                  <span className="text-gray-400">{doc.chunk_count} chunks</span>
                  <span className="px-2 py-0.5 bg-emerald-50 text-emerald-600 font-semibold rounded-full text-[11px]">
                    {doc.status}
                  </span>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => handleView(doc.id)}
                    className="px-4 py-2 bg-blue-500 text-white text-sm font-medium rounded-md
                               hover:bg-blue-600 hover:scale-105 transition-all duration-200"
                  >
                    查看文档
                  </button>
                  <button
                    onClick={() => handleDelete(doc.id)}
                    className="px-4 py-2 text-sm font-medium text-gray-400 rounded-md
                               hover:text-red-500 hover:bg-red-50 transition-all duration-200"
                  >
                    删除
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 文档详情模态框 */}
      {viewing && (
        <div
          className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center"
          style={{ animation: "fadeIn 0.15s ease" }}
          onClick={() => setViewing(null)}
        >
          <div
            className="bg-white rounded-lg w-[90vw] max-w-2xl max-h-[85vh] flex flex-col"
            style={{ animation: "slideUp 0.2s ease" }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* 模态框头部 —— 彩色块 */}
            <div className="bg-blue-500 text-white px-6 py-4 rounded-t-lg flex items-start justify-between">
              <div className="min-w-0 mr-4">
                <h3 className="font-bold text-lg leading-snug">{viewing.title}</h3>
                <p className="text-blue-100 text-sm mt-1">
                  {viewing.chunk_count} 个章节
                  {viewing.source_url && (() => {
                    const cleaned = cleanUrl(viewing.source_url);
                    return cleaned ? (
                      <span className="ml-3">
                        <a
                          href={cleaned}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-blue-100 hover:text-white transition-colors"
                        >
                          <ExternalLink size={12} />
                          查看原文
                        </a>
                      </span>
                    ) : null;
                  })()}
                </p>
              </div>
              <button
                onClick={() => setViewing(null)}
                className="w-8 h-8 bg-white/20 rounded-md flex items-center justify-center
                           hover:bg-white/30 transition-colors flex-shrink-0"
              >
                <X size={16} />
              </button>
            </div>

            {/* 模态框内容 */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {viewing.chunks.map((chunk, i) => (
                <div key={`${chunk.chunk_id}_${i}`}>
                  <h4 className="text-sm font-bold text-blue-500 mb-2 pb-1.5 border-b-2 border-gray-100">
                    {chunk.section_path || "正文"}
                  </h4>
                  <pre className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap font-mono bg-gray-50 rounded-md p-4">
                    {chunk.content}
                  </pre>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 加载遮罩 */}
      {viewLoading && (
        <div
          className="fixed inset-0 bg-black/50 z-[60] flex items-center justify-center"
          style={{ animation: "fadeIn 0.15s ease" }}
        >
          <div className="bg-white rounded-md px-8 py-5 text-sm font-medium text-gray-500">
            <RefreshCw size={18} className="animate-spin inline mr-2" />
            加载中...
          </div>
        </div>
      )}

      {/* Toast 通知 */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-[70] flex flex-col gap-2">
          <div
            className={`px-5 py-3 rounded-md text-sm font-medium text-white ${
              toast.type === "success" ? "bg-emerald-500" : "bg-red-500"
            }`}
            style={{ animation: "slideIn 0.2s ease" }}
          >
            {toast.msg}
          </div>
        </div>
      )}
    </div>
  );
}
