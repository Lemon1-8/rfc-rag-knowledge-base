import ReactMarkdown from "react-markdown";
import type { Message } from "../../hooks/useChat";

interface Props {
  message: Message;
}

export default function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";

  return (
    <div className={`message ${isUser ? "user" : "assistant"}`}>
      <div className="message-avatar">{isUser ? "U" : "AI"}</div>
      <div className="message-body">
        <div className="message-content">
          {isUser ? (
            <p>{message.content}</p>
          ) : (
            <ReactMarkdown>{message.content}</ReactMarkdown>
          )}
          {message.isStreaming && <span className="cursor-blink" />}
        </div>
        {message.sources && message.sources.length > 0 && (
          <div className="message-sources">
            <details>
              <summary>引用来源 ({message.sources.length})</summary>
              <ul>
                {message.sources.map((s, i) => (
                  <li key={i}>
                    {s.url ? (
                      <a href={s.url} target="_blank" rel="noopener noreferrer">
                        [{i + 1}] {s.title} — {s.section}
                      </a>
                    ) : (
                      <span>
                        [{i + 1}] {s.title} — {s.section}
                      </span>
                    )}
                    <span className="score">
                      {s.score.toFixed(2)}
                    </span>
                  </li>
                ))}
              </ul>
            </details>
          </div>
        )}
      </div>
    </div>
  );
}
