import { useState } from "react";
import ChatWindow from "./components/Chat/ChatWindow";
import DocumentManager from "./components/DocumentManager";
import SearchPanel from "./components/Search";
import "./App.css";

type Tab = "chat" | "docs" | "search";

function App() {
  const [activeTab, setActiveTab] = useState<Tab>("chat");

  const tabs: { key: Tab; label: string }[] = [
    { key: "chat", label: "对话" },
    { key: "docs", label: "文档" },
    { key: "search", label: "检索" },
  ];

  return (
    <div className="app">
      <aside className="sidebar">
        <h1 className="sidebar-title">RFC RAG</h1>
        <nav className="sidebar-nav">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              className={`nav-btn ${activeTab === tab.key ? "active" : ""}`}
              onClick={() => setActiveTab(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <p>DeepSeek-V3</p>
          <p>BGE-M3</p>
        </div>
      </aside>
      <main className="main">
        {activeTab === "chat" && <ChatWindow />}
        {activeTab === "docs" && <DocumentManager />}
        {activeTab === "search" && <SearchPanel />}
      </main>
    </div>
  );
}

export default App;
