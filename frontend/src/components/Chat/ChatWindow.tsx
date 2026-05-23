import { useEffect, useRef } from "react";
import { useChat } from "../../hooks/useChat";
import MessageBubble from "./MessageBubble";
import ChatInput from "./ChatInput";

export default function ChatWindow() {
  const { messages, isLoading, sendMessage, clearChat } = useChat();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="chat-window">
      <div className="chat-header">
        <h2>RFC 知识库问答</h2>
        <button className="btn-clear" onClick={clearChat} disabled={isLoading}>
          清空对话
        </button>
      </div>
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            <h3>RFC 技术文档 RAG 知识库</h3>
            <p>基于 DeepSeek-V3 + BGE-M3，你可以问：</p>
            <div className="example-queries">
              {[
                "HTTP/2 的多路复用是如何实现的？",
                "QUIC 协议相比 TCP 有哪些优势？",
                "TLS 1.3 握手过程是怎样的？",
              ].map((q) => (
                <button key={q} onClick={() => sendMessage(q)}>
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        <div ref={bottomRef} />
      </div>
      <ChatInput onSend={sendMessage} isLoading={isLoading} />
    </div>
  );
}
