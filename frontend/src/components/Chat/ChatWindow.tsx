import { useEffect, useRef } from "react";
import { MessageSquare, Cpu, Zap } from "lucide-react";
import type { Message } from "../../hooks/useChat";
import MessageBubble from "./MessageBubble";
import ChatInput from "./ChatInput";

interface Props {
  messages: Message[];
  isLoading: boolean;
  conversationId?: string;
  onSend: (query: string) => void;
  onClear: () => void;
}

const exampleQueries = [
  {
    icon: MessageSquare,
    color: "blue",
    text: "HTTP/2 的多路复用是如何实现的？",
  },
  {
    icon: Cpu,
    color: "emerald",
    text: "QUIC 协议相比 TCP 有哪些优势？",
  },
  {
    icon: Zap,
    color: "amber",
    text: "TLS 1.3 握手过程是怎样的？",
  },
] as const;

const colorMap = {
  blue: { bg: "bg-blue-50", hover: "hover:bg-blue-100", icon: "text-blue-500" },
  emerald: {
    bg: "bg-emerald-50",
    hover: "hover:bg-emerald-100",
    icon: "text-emerald-500",
  },
  amber: {
    bg: "bg-amber-50",
    hover: "hover:bg-amber-100",
    icon: "text-amber-500",
  },
};

export default function ChatWindow({
  messages,
  isLoading,
  onSend,
}: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto">
        {messages.length === 0 ? (
          /* 空状态 —— 几何装饰 + 示例卡片 */
          <div className="h-full flex items-center justify-center relative overflow-hidden">
            {/* 背景几何装饰 */}
            <div className="absolute -top-40 -right-40 w-[500px] h-[500px] rounded-full bg-blue-50/60" />
            <div className="absolute -bottom-32 -left-32 w-80 h-80 bg-emerald-50/60 rotate-45" />
            <div className="absolute top-1/3 left-1/4 w-40 h-40 rounded-full bg-amber-50/50" />

            <div className="relative z-10 text-center max-w-2xl px-8 py-12">
              <h1 className="text-3xl font-extrabold tracking-tight text-gray-900 mb-2">
                RFC 技术文档知识库
              </h1>
              <p className="text-gray-500 text-base mb-12">
                基于 DeepSeek-V3 + BGE-M3 的 RAG 智能问答系统
              </p>

              <div className="grid grid-cols-3 gap-4">
                {exampleQueries.map(({ icon: Icon, color, text }) => {
                  const c = colorMap[color];
                  return (
                    <button
                      key={text}
                      onClick={() => onSend(text)}
                      className={`group ${c.bg} ${c.hover} rounded-lg p-5 text-left transition-all duration-200 hover:scale-[1.02]`}
                    >
                      <div className="w-10 h-10 bg-white rounded-full flex items-center justify-center mb-3 group-hover:scale-110 transition-transform duration-200">
                        <Icon size={18} className={c.icon} />
                      </div>
                      <p className="text-sm font-medium text-gray-800 leading-relaxed">
                        {text}
                      </p>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        ) : (
          /* 消息列表 */
          <div className="max-w-3xl mx-auto px-6 py-6 space-y-6">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      <ChatInput onSend={onSend} isLoading={isLoading} />
    </div>
  );
}
