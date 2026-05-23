const API_BASE = "http://localhost:8000";

export interface Source {
  document_id: string;
  title: string;
  section: string;
  content_preview: string;
  url: string;
  score: number;
}

export interface ChatEvent {
  type: "token" | "sources" | "done" | "error";
  content?: string;
  documents?: Source[];
  message?: string;
}

export async function* streamChat(
  query: string,
  topK: number = 5
): AsyncGenerator<ChatEvent> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, top_k: topK }),
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
): Promise<any[]> {
  const res = await fetch(
    `${API_BASE}/api/search?q=${encodeURIComponent(q)}&top_k=${topK}`
  );
  const data = await res.json();
  return data.results || [];
}

export async function deleteDocument(id: string): Promise<void> {
  await fetch(`${API_BASE}/api/documents/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}
