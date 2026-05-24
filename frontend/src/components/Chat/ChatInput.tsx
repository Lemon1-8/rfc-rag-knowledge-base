import { useState, useRef, KeyboardEvent } from "react";
import { Send, Loader2 } from "lucide-react";

interface Props {
  onSend: (query: string) => void;
  isLoading: boolean;
}

export default function ChatInput({ onSend, isLoading }: Props) {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed || isLoading) return;
    onSend(trimmed);
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  };

  const canSend = input.trim().length > 0 && !isLoading;

  return (
    <div className="border-t-2 border-gray-100 p-4 bg-white">
      <div className="max-w-3xl mx-auto flex gap-2">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder="输入你的问题，例如：HTTP/2 多路复用原理是什么？"
          rows={1}
          disabled={isLoading}
          className="flex-1 bg-gray-100 rounded-md px-4 py-3 text-sm resize-none
                     focus:bg-white focus:border-2 focus:border-blue-500 focus:outline-none
                     transition-all duration-200 placeholder:text-gray-400
                     disabled:opacity-50 disabled:cursor-not-allowed
                     text-gray-900"
          style={{ fontFamily: "inherit" }}
        />
        <button
          onClick={handleSend}
          disabled={!canSend}
          className="h-12 w-12 bg-blue-500 text-white rounded-md
                     hover:bg-blue-600 hover:scale-105
                     transition-all duration-200 flex items-center justify-center flex-shrink-0
                     disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:scale-100"
        >
          {isLoading ? (
            <Loader2 size={18} className="animate-spin" />
          ) : (
            <Send size={18} />
          )}
        </button>
      </div>
    </div>
  );
}
