import { useState, useEffect } from "react";
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
    <div className="panel">
      <div className="panel-header">
        <h3>文档管理</h3>
        <div className="panel-header-actions">
          <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
            {docs.length} 个文档
          </span>
          <button className="btn-secondary" onClick={loadDocs} disabled={loading}>
            {loading ? "加载中..." : "刷新"}
          </button>
        </div>
      </div>

      <div className="panel-body">
        {loading && (
          <div className="doc-grid">
            {[1, 2, 3].map((i) => (
              <div key={i} className="skeleton skeleton-card" />
            ))}
          </div>
        )}

        {!loading && docs.length === 0 && (
          <div className="empty-state">
            <div className="empty-icon">📂</div>
            <p>暂无文档，请先运行数据管道</p>
          </div>
        )}

        {!loading && docs.length > 0 && (
          <div className="doc-grid">
            {docs.map((doc) => (
              <div key={doc.id} className="doc-card">
                <div className="doc-card-header">
                  <span className="doc-card-title">{doc.title}</span>
                  <span className="doc-card-badge">{doc.status}</span>
                </div>
                <div className="doc-card-meta">
                  <span>{doc.chunk_count} chunks</span>
                </div>
                <div className="doc-card-actions">
                  <button
                    className="btn-sm btn-sm-primary"
                    onClick={() => handleView(doc.id)}
                  >
                    查看文档
                  </button>
                  <button
                    className="btn-sm btn-sm-danger"
                    onClick={() => handleDelete(doc.id)}
                  >
                    删除
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 文档查看 Modal */}
      {viewing && (
        <div className="modal-overlay" onClick={() => setViewing(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h3>{viewing.title}</h3>
                <div className="modal-meta">
                  {viewing.chunk_count} 个章节 ·{" "}
                  {viewing.source_url && (() => {
                    const cleaned = cleanUrl(viewing.source_url);
                    return cleaned ? (
                      <a
                        href={cleaned}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ color: "var(--accent)" }}
                      >
                        查看原文
                      </a>
                    ) : null;
                  })()}
                </div>
              </div>
              <button className="btn-close" onClick={() => setViewing(null)}>
                ✕
              </button>
            </div>
            <div className="modal-body">
              {viewing.chunks.map((chunk, i) => (
                <div key={`${chunk.chunk_id}_${i}`} className="doc-section">
                  <div className="section-title">
                    {chunk.section_path || "正文"}
                  </div>
                  <div className="section-content">{chunk.content}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 加载 Modal 的遮罩 */}
      {viewLoading && (
        <div className="modal-overlay">
          <div
            style={{
              color: "var(--text-secondary)",
              fontSize: 14,
              background: "var(--bg-secondary)",
              padding: "20px 40px",
              borderRadius: "var(--radius)",
              border: "1px solid var(--border)",
            }}
          >
            加载中...
          </div>
        </div>
      )}

      {/* Toast */}
      {toast && (
        <div className="toast-container">
          <div className={`toast ${toast.type}`}>{toast.msg}</div>
        </div>
      )}
    </div>
  );
}
