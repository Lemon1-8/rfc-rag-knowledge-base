import { useState, useEffect } from "react";
import { fetchDocuments, deleteDocument } from "../../api/client";

export default function DocumentManager() {
  const [docs, setDocs] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const loadDocs = async () => {
    setLoading(true);
    try {
      const data = await fetchDocuments();
      setDocs(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDocs();
  }, []);

  const handleDelete = async (id: string) => {
    if (!confirm("确定删除？")) return;
    try {
      await deleteDocument(id);
      setDocs((prev) => prev.filter((d) => d.id !== id));
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="panel">
      <div className="panel-header">
        <h3>文档管理</h3>
        <button onClick={loadDocs} disabled={loading}>
          {loading ? "加载中..." : "刷新"}
        </button>
      </div>
      <div className="panel-body">
        {docs.length === 0 && <p className="empty">暂无文档</p>}
        <ul className="doc-list">
          {docs.map((doc) => (
            <li key={doc.id}>
              <div className="doc-info">
                <span className="doc-title">{doc.title}</span>
                <span className="doc-meta">
                  {doc.chunk_count} chunks · {doc.status}
                </span>
              </div>
              <button
                className="btn-delete"
                onClick={() => handleDelete(doc.id)}
              >
                删除
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
