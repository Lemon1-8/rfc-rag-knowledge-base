import { useState, useRef, useCallback } from "react";
import {
  streamChat,
  fetchConversation,
  type Source,
} from "../api/client";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  isStreaming?: boolean;
}

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    async (query: string) => {
      const userMsg: Message = {
        id: Date.now().toString(),
        role: "user",
        content: query,
      };
      const assistantMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: "",
        isStreaming: true,
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setIsLoading(true);

      try {
        for await (const event of streamChat(query, conversationId)) {
          switch (event.type) {
            case "token":
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantMsg.id && m.isStreaming
                    ? { ...m, content: m.content + (event.content || "") }
                    : m
                )
              );
              break;
            case "sources":
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantMsg.id
                    ? { ...m, sources: event.documents }
                    : m
                )
              );
              break;
            case "conversation_id":
              if (event.conversation_id && !conversationId) {
                setConversationId(event.conversation_id);
              }
              break;
            case "error":
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantMsg.id && m.isStreaming
                    ? {
                        ...m,
                        content: m.content + `\n\n[错误] ${event.message}`,
                        isStreaming: false,
                      }
                    : m
                )
              );
              break;
            case "done":
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantMsg.id
                    ? { ...m, isStreaming: false }
                    : m
                )
              );
              break;
          }
        }
      } catch (err: any) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsg.id && m.isStreaming
              ? {
                  ...m,
                  content: m.content + `\n\n[连接错误] ${err.message}`,
                  isStreaming: false,
                }
              : m
          )
        );
      } finally {
        setIsLoading(false);
      }
    },
    [conversationId]
  );

  /** 从后端加载对话历史 */
  const loadConversation = useCallback(async (convId: string) => {
    try {
      const detail = await fetchConversation(convId);
      setConversationId(convId);
      setMessages(
        detail.messages.map((m) => ({
          id: m.id.toString(),
          role: m.role as "user" | "assistant",
          content: m.content,
          sources: m.sources,
        }))
      );
    } catch {
      // 对话不存在，重置
      setConversationId(undefined);
      setMessages([]);
    }
  }, []);

  /** 开始新对话 */
  const newConversation = useCallback(() => {
    setConversationId(undefined);
    setMessages([]);
  }, []);

  const clearChat = useCallback(() => {
    setMessages([]);
  }, []);

  return {
    messages,
    isLoading,
    conversationId,
    sendMessage,
    clearChat,
    loadConversation,
    newConversation,
  };
}
