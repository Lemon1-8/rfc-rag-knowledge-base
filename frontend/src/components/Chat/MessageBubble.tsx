import ReactMarkdown from "react-markdown";
import type { Message } from "../../hooks/useChat";

interface Props {
  message: Message;
}

/** 清理数据库中残留的脏 URL */
function cleanUrl(url: string): string {
  return url.replace(/^[:\s]+/, "").trim();
}

export default function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] bg-blue-500 text-white rounded-lg px-5 py-3">
          <p className="text-sm leading-relaxed whitespace-pre-wrap">
            {message.content}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-3">
      <div className="w-8 h-8 bg-gray-200 rounded-md flex items-center justify-center flex-shrink-0 mt-0.5">
        <span className="text-xs font-extrabold text-gray-500">AI</span>
      </div>
      <div className="min-w-0">
        <div className="message-markdown text-sm text-gray-800 leading-relaxed">
          <ReactMarkdown>{message.content}</ReactMarkdown>
          {message.isStreaming && <span className="cursor-blink" />}
        </div>

        {message.sources && message.sources.length > 0 && (
          <details className="mt-2">
            <summary className="text-xs text-gray-400 cursor-pointer hover:text-gray-600 transition-colors font-medium select-none">
              引用来源 ({message.sources.length})
            </summary>
            <div className="mt-2 bg-gray-50 rounded-md p-3 space-y-1">
              {message.sources.map((s, i) => (
                <div
                  key={i}
                  className="flex justify-between items-center py-1 text-xs"
                >
                  {s.url ? (
                    <a
                      href={cleanUrl(s.url)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-500 hover:underline truncate mr-2"
                    >
                      [{i + 1}] {s.title} — {s.section}
                    </a>
                  ) : (
                    <span className="text-gray-600 truncate mr-2">
                      [{i + 1}] {s.title} — {s.section}
                    </span>
                  )}
                  <span className="text-gray-400 font-mono flex-shrink-0 text-[11px]">
                    {s.score.toFixed(2)}
                  </span>
                </div>
              ))}
            </div>
          </details>
        )}
      </div>
    </div>
  );
}
