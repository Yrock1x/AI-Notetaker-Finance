"use client";

import { useState } from "react";
import { useAskQuestion } from "@/hooks/use-qa";
import { LoadingState } from "@/components/shared/loading-state";
import { Send, MessageCircle, BookOpen } from "lucide-react";

interface QAChatProps {
  dealId: string;
}

interface QAEntry {
  question: string;
  answer: string;
  citations: Array<{
    source_type: string;
    source_id: string;
    source_title: string;
    excerpt: string;
    timestamp?: number;
    page_number?: number;
    confidence: number;
  }>;
  processing_time_ms?: number;
}

export function QAChat({ dealId }: QAChatProps) {
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState<QAEntry[]>([]);
  const askQuestion = useAskQuestion();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || askQuestion.isPending) return;

    const q = question.trim();
    setQuestion("");

    try {
      const response = await askQuestion.mutateAsync({
        dealId,
        payload: { question: q },
      });
      setHistory((prev) => [
        ...prev,
        {
          question: q,
          answer: response.answer,
          citations: response.citations,
          processing_time_ms: response.processing_time_ms,
        },
      ]);
    } catch {
      setHistory((prev) => [
        ...prev,
        {
          question: q,
          answer: "Sorry, an error occurred while processing your question.",
          citations: [],
        },
      ]);
    }
  };

  return (
    <div className="flex flex-col rounded-lg border bg-white">
      {/* Chat history */}
      <div className="min-h-[400px] max-h-[600px] overflow-y-auto p-4 space-y-6">
        {history.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <MessageCircle className="h-12 w-12 text-muted-foreground/30" />
            <h3 className="mt-4 text-lg font-medium">Ask a question</h3>
            <p className="mt-1 max-w-sm text-sm text-muted-foreground">
              Questions are answered using meeting transcripts and documents
              from this deal, with source citations.
            </p>
            <div className="mt-6 space-y-2">
              <p className="text-xs font-medium text-muted-foreground">
                Example questions:
              </p>
              {[
                "What are the key financial metrics discussed?",
                "What risks were identified in the due diligence?",
                "Summarize the management team's growth strategy",
              ].map((example) => (
                <button
                  key={example}
                  onClick={() => setQuestion(example)}
                  className="block w-full rounded-md border px-3 py-2 text-left text-sm hover:bg-muted"
                >
                  {example}
                </button>
              ))}
            </div>
          </div>
        ) : (
          history.map((entry, i) => (
            <div key={i} className="space-y-3">
              {/* Question */}
              <div className="flex justify-end">
                <div className="max-w-[80%] rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground">
                  {entry.question}
                </div>
              </div>
              {/* Answer */}
              <div className="space-y-2">
                <div className="max-w-[90%] rounded-lg bg-muted px-4 py-3 text-sm">
                  <p className="whitespace-pre-wrap">{entry.answer}</p>
                </div>
                {/* Citations */}
                {entry.citations.length > 0 && (
                  <div className="ml-2 space-y-1">
                    <p className="flex items-center gap-1 text-xs font-medium text-muted-foreground">
                      <BookOpen className="h-3 w-3" />
                      Sources ({entry.citations.length})
                    </p>
                    {entry.citations.map((citation, j) => (
                      <div
                        key={j}
                        className="rounded border bg-white px-3 py-2 text-xs"
                      >
                        <p className="font-medium">{citation.source_title}</p>
                        <p className="mt-0.5 text-muted-foreground line-clamp-2">
                          {citation.excerpt}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
                {entry.processing_time_ms != null && (
                  <p className="ml-2 text-xs text-muted-foreground">
                    Processed in {(entry.processing_time_ms / 1000).toFixed(1)}s
                  </p>
                )}
              </div>
            </div>
          ))
        )}

        {askQuestion.isPending && (
          <div className="flex justify-start">
            <div className="rounded-lg bg-muted px-4 py-3">
              <LoadingState message="Thinking..." />
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="border-t p-4">
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask a question about this deal..."
            className="flex-1 rounded-md border px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
            disabled={askQuestion.isPending}
          />
          <button
            type="submit"
            disabled={!question.trim() || askQuestion.isPending}
            className="rounded-md bg-primary p-2 text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      </form>
    </div>
  );
}
