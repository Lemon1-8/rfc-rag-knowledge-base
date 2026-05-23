import { useState, useEffect, useCallback } from "react";
import ChatWindow from "./components/Chat/ChatWindow";
import DocumentManager from "./components/DocumentManager";
import SearchPanel from "./components/Search";
import { useChat } from "./hooks/useChat";
import {
  fetchConversations,
  fetchConversation,
  createConversation,
  deleteConversation,
  type Conversation,
} from "./api/client";
import "./App.css";

type Tab = "chat" | "docs" | "search";

const tabs: { key: Tab; label: string; icon: string }[] = [
  { key: "chat", label: "对话", icon: "💬" },
  { key: "docs", label: "文档", icon: "📄" },
  { key: "search", label: "检索", icon: "🔍" },
];

function App() {
  const [activeTab, setActiveTab] = useState<Tab>("chat");
  const chat = useChat();
  const [convs, setConvs] = useState<Conversation[]>([]);

  const loadConvList = useCallback(async () => {
    try {
      setConvs(await fetchConversations());
    } catch {}
  }, []);

  useEffect(() => {
    loadConvList();
  }, [loadConvList]);

  // 对话切换时刷新列表
  useEffect(() => {
    loadConvList();
  }, [chat.conversationId]);

  const handleSelectConv = async (id: string) => {
    await chat.loadConversation(id);
    setActiveTab("chat");
  };

  const handleNewConv = () => {
    chat.newConversation();
    setActiveTab("chat");
  };

  const handleDeleteConv = async (id: string) => {
    if (!confirm("确定删除此对话？")) return;
    try {
      await deleteConversation(id);
      if (chat.conversationId === id) {
        chat.newConversation();
      }
      loadConvList();
    } catch {}
  };

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-brand">
          <div className="brand-icon">R</div>
          RFC RAG
        </div>
        <div className="header-status">
          <span>
            <span className="status-dot online" />
            DeepSeek-V3
          </span>
          <span>
            <span className="status-dot online" />
            BGE-M3
          </span>
        </div>
      </header>

      <aside className="sidebar">
        <div className="sidebar-label">导航</div>
        <nav className="sidebar-nav">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              className={`nav-btn ${activeTab === tab.key ? "active" : ""}`}
              onClick={() => setActiveTab(tab.key)}
            >
              <span className="nav-icon">{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </nav>

        <div className="sidebar-label">历史对话</div>
        <button className="btn-new-chat" onClick={handleNewConv}>
          + 新对话
        </button>
        <div className="conv-list">
          {convs.map((c) => (
            <div
              key={c.id}
              className={`conv-item ${chat.conversationId === c.id ? "active" : ""}`}
            >
              <span className="conv-title" onClick={() => handleSelectConv(c.id)}>
                {c.title}
              </span>
              <button
                className="conv-delete"
                onClick={(e) => {
                  e.stopPropagation();
                  handleDeleteConv(c.id);
                }}
              >
                ✕
              </button>
            </div>
          ))}
          {convs.length === 0 && (
            <div className="conv-empty">暂无历史对话</div>
          )}
        </div>

        <div className="sidebar-footer">
          RFC 技术文档
          <br />
          RAG 知识库
        </div>
      </aside>

      <main className="main">
        {activeTab === "chat" && (
          <ChatWindow
            messages={chat.messages}
            isLoading={chat.isLoading}
            conversationId={chat.conversationId}
            onSend={chat.sendMessage}
            onClear={chat.clearChat}
          />
        )}
        {activeTab === "docs" && <DocumentManager />}
        {activeTab === "search" && <SearchPanel />}
      </main>
    </div>
  );
}

export default App;
