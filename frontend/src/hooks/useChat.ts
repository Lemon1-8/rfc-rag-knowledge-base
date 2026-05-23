import { useState, useRef, useCallback } from "react";
import { streamChat } from "../api/client";
import type { Source } from "../api/client";

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
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(async (query: string) => {
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
      for await (const event of streamChat(query)) {
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
  }, []);

  const clearChat = useCallback(() => {
    setMessages([]);
  }, []);

  return { messages, isLoading, sendMessage, clearChat };
}
