const API_BASE = "http://localhost:8001";

export interface Source {
  document_id: string;
  title: string;
  section: string;
  content_preview: string;
  url: string;
  score: number;
}

export interface ChatEvent {
  type: "token" | "sources" | "done" | "error" | "conversation_id";
  content?: string;
  documents?: Source[];
  message?: string;
  conversation_id?: string;
}

export async function* streamChat(
  query: string,
  conversationId?: string,
  topK: number = 5
): AsyncGenerator<ChatEvent> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query,
      conversation_id: conversationId,
      top_k: topK,
    }),
  });

  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      const match = line.match(/^data: (.+)$/m);
      if (match) {
        try {
          yield JSON.parse(match[1]);
        } catch {
          // skip malformed
        }
      }
    }
  }
}

export async function fetchDocuments(): Promise<any[]> {
  const res = await fetch(`${API_BASE}/api/documents`);
  const data = await res.json();
  return data.documents || [];
}

export async function searchDocuments(
  q: string,
  topK: number = 5
): Promise<{ results: any[]; query_time_ms: number }> {
  const res = await fetch(
    `${API_BASE}/api/search?q=${encodeURIComponent(q)}&top_k=${topK}`
  );
  const data = await res.json();
  return { results: data.results || [], query_time_ms: data.query_time_ms || 0 };
}

export interface DocumentChunk {
  chunk_id: string;
  section_path: string;
  content: string;
}

export interface DocumentDetail {
  id: string;
  title: string;
  source_url: string;
  chunks: DocumentChunk[];
  chunk_count: number;
}

export async function fetchDocumentContent(
  id: string
): Promise<DocumentDetail> {
  const res = await fetch(
    `${API_BASE}/api/documents/${encodeURIComponent(id)}`
  );
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function deleteDocument(id: string): Promise<void> {
  await fetch(`${API_BASE}/api/documents/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

// --- Conversations ---

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: MessageRecord[];
}

export interface MessageRecord {
  id: number;
  role: "user" | "assistant";
  content: string;
  sources: Source[];
  created_at: string;
}

export async function fetchConversations(): Promise<Conversation[]> {
  const res = await fetch(`${API_BASE}/api/conversations`);
  const data = await res.json();
  return data.conversations || [];
}

export async function fetchConversation(
  id: string
): Promise<ConversationDetail> {
  const res = await fetch(
    `${API_BASE}/api/conversations/${encodeURIComponent(id)}`
  );
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function createConversation(
  title?: string
): Promise<ConversationDetail> {
  const res = await fetch(`${API_BASE}/api/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(title ? { title } : {}),
  });
  return res.json();
}

export async function deleteConversation(id: string): Promise<void> {
  await fetch(`${API_BASE}/api/conversations/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}
