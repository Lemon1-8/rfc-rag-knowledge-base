import { useState, useEffect, useCallback } from "react";
import {
  MessageSquare,
  FileText,
  Search,
  Plus,
  Trash2,
} from "lucide-react";
import ChatWindow from "./components/Chat/ChatWindow";
import DocumentManager from "./components/DocumentManager";
import SearchPanel from "./components/Search";
import { useChat } from "./hooks/useChat";
import {
  fetchConversations,
  deleteConversation,
  type Conversation,
} from "./api/client";
import "./App.css";

type Tab = "chat" | "docs" | "search";

const tabs: { key: Tab; label: string; icon: typeof MessageSquare }[] = [
  { key: "chat", label: "对话", icon: MessageSquare },
  { key: "docs", label: "文档", icon: FileText },
  { key: "search", label: "检索", icon: Search },
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
    <div className="h-screen flex flex-col bg-white">
      {/* 顶栏 */}
      <header className="h-14 flex items-center justify-between px-6 bg-white border-b-2 border-gray-100 flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 bg-blue-500 rounded-md flex items-center justify-center">
            <span className="text-white font-extrabold text-xs">R</span>
          </div>
          <span className="font-extrabold text-lg tracking-tight text-gray-900">
            RFC RAG
          </span>
        </div>
        <div className="flex items-center gap-5 text-sm text-gray-500">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            DeepSeek-V3
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            BGE-M3
          </span>
        </div>
      </header>

      <div className="flex-1 flex overflow-hidden">
        {/* 侧边栏 */}
        <aside className="w-56 flex-shrink-0 bg-gray-100 flex flex-col">
          <div className="p-4 pb-2">
            <p className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3 px-2">
              导航
            </p>
            <nav className="flex flex-col gap-0.5">
              {tabs.map(({ key, label, icon: Icon }) => (
                <button
                  key={key}
                  onClick={() => setActiveTab(key)}
                  className={`flex items-center gap-2.5 w-full text-left px-3 py-2 rounded-md text-sm font-medium transition-all duration-200 ${
                    activeTab === key
                      ? "bg-white text-blue-500"
                      : "text-gray-500 hover:text-gray-900 hover:bg-gray-200/70"
                  }`}
                >
                  <Icon size={17} />
                  {label}
                </button>
              ))}
            </nav>
          </div>

          <div className="px-4 pt-4 pb-2">
            <p className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3 px-2">
              历史对话
            </p>
            <button
              onClick={handleNewConv}
              className="flex items-center gap-2 w-full px-3 py-2 rounded-md text-sm font-medium text-gray-500 hover:text-blue-500 hover:bg-blue-50 transition-all duration-200"
            >
              <Plus size={16} />
              新对话
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-4 pb-2">
            {convs.map((c) => (
              <div
                key={c.id}
                className={`group flex items-center gap-1 px-3 py-1.5 rounded-md cursor-pointer transition-all duration-200 ${
                  chat.conversationId === c.id
                    ? "bg-white text-blue-500 font-medium"
                    : "text-gray-600 hover:bg-gray-200/70"
                }`}
              >
                <span
                  className="flex-1 text-sm truncate"
                  onClick={() => handleSelectConv(c.id)}
                >
                  {c.title}
                </span>
                <button
                  className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-100 hover:text-red-500 transition-all duration-200 flex-shrink-0"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDeleteConv(c.id);
                  }}
                >
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
            {convs.length === 0 && (
              <p className="text-xs text-gray-400 text-center py-6">
                暂无历史对话
              </p>
            )}
          </div>

          <div className="p-4 border-t-2 border-gray-200">
            <p className="text-xs text-gray-400 leading-relaxed">
              RFC 技术文档
              <br />
              RAG 知识库
            </p>
          </div>
        </aside>

        {/* 主内容区 */}
        <main className="flex-1 overflow-auto bg-white">
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
    </div>
  );
}

export default App;
