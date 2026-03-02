"use client";

import { useState, useRef, useEffect } from "react";
import { useDeliverableChat } from "@/hooks/use-deliverables";
import { Send, Sparkles, Loader2 } from "lucide-react";

interface DeliverableChatProps {
  dealId: string;
}

interface ChatEntry {
  role: "user" | "assistant";
  content: string;
}

const EXAMPLE_PROMPTS = [
  "Draft an investment memo focusing on the competitive moat",
  "Build a financial model with bear/base/bull scenarios",
  "Create an IC deck emphasizing the market opportunity",
];

export function DeliverableChat({ dealId }: DeliverableChatProps) {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatEntry[]>([]);
  const chatMutation = useDeliverableChat();
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, chatMutation.isPending]);

  const handleSend = async (text?: string) => {
    const msg = (text ?? input).trim();
    if (!msg || chatMutation.isPending) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: msg }]);

    try {
      const response = await chatMutation.mutateAsync({
        dealId,
        message: msg,
      });
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: response.content },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content:
            "Sorry, something went wrong. Please try again.",
        },
      ]);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSend();
  };

  return (
    <div className="rounded-2xl border border-[#1A1A1A]/5 bg-white overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2.5 border-b border-[#1A1A1A]/5 px-5 py-3.5">
        <div className="rounded-lg bg-accent/10 p-1.5">
          <Sparkles className="h-4 w-4 text-accent" />
        </div>
        <div>
          <p className="text-sm font-bold text-primary">AI Assistant</p>
          <p className="text-[11px] text-[#1A1A1A]/40">
            Describe what you need — I&apos;ll help shape your deliverable
          </p>
        </div>
      </div>

      {/* Messages area */}
      <div className="min-h-[300px] max-h-[460px] overflow-y-auto px-5 py-4 space-y-4">
        {messages.length === 0 && !chatMutation.isPending ? (
          <div className="flex flex-col items-center justify-center py-10 text-center">
            <div className="rounded-2xl bg-[#F2F0E9]/60 p-4">
              <Sparkles className="h-7 w-7 text-[#1A1A1A]/20" />
            </div>
            <p className="mt-4 text-sm font-bold text-primary/70">
              What would you like to create?
            </p>
            <p className="mt-1 max-w-xs text-xs text-[#1A1A1A]/40">
              Describe the deliverable you need — include context on audience,
              focus areas, or specific sections.
            </p>
            <div className="mt-5 w-full max-w-sm space-y-2">
              {EXAMPLE_PROMPTS.map((example) => (
                <button
                  key={example}
                  onClick={() => handleSend(example)}
                  className="block w-full rounded-xl border border-[#1A1A1A]/5 bg-[#F2F0E9]/30 px-4 py-2.5 text-left text-xs font-medium text-[#1A1A1A]/60 transition-all hover:border-accent/30 hover:text-accent"
                >
                  {example}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {messages.map((entry, i) => (
              <div
                key={i}
                className={`flex ${
                  entry.role === "user" ? "justify-end" : "justify-start"
                }`}
              >
                <div
                  className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm ${
                    entry.role === "user"
                      ? "bg-accent text-white"
                      : "bg-[#F2F0E9]/60 text-primary"
                  }`}
                >
                  <p className="whitespace-pre-wrap leading-relaxed">
                    {entry.content}
                  </p>
                </div>
              </div>
            ))}

            {chatMutation.isPending && (
              <div className="flex justify-start">
                <div className="flex items-center gap-2 rounded-2xl bg-[#F2F0E9]/60 px-4 py-3">
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-accent" />
                  <span className="text-xs font-medium text-[#1A1A1A]/40">
                    Thinking...
                  </span>
                </div>
              </div>
            )}
          </>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* Input */}
      <form
        onSubmit={handleSubmit}
        className="border-t border-[#1A1A1A]/5 px-4 py-3"
      >
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Describe what you'd like to generate..."
            className="flex-1 rounded-xl border border-[#1A1A1A]/10 bg-[#F2F0E9]/20 px-4 py-2.5 text-sm text-primary placeholder:text-[#1A1A1A]/30 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent/30"
            disabled={chatMutation.isPending}
          />
          <button
            type="submit"
            disabled={!input.trim() || chatMutation.isPending}
            className="rounded-xl bg-accent p-2.5 text-white shadow-sm transition-all hover:shadow-md disabled:opacity-40"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      </form>
    </div>
  );
}
