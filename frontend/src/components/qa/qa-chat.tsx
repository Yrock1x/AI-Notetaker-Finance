"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { useAskQuestion, useMeetingAskQuestion } from "@/hooks/use-qa";
import { LoadingState } from "@/components/shared/loading-state";
import { Send, MessageCircle, BookOpen } from "lucide-react";

type QAChatScope =
  | { scope: "deal"; dealId: string }
  | { scope: "meeting"; meetingId: string; dealId: string };

// `fillHeight` makes the chat stretch to its parent's height (the internal
// message scroller becomes `flex-1 min-h-0` and the outer card grows with
// `h-full`). The meeting detail page passes this for the Live split-pane
// and the AI Chat tab; deal-level / global chat pages leave it off so the
// default clamped height preserves today's look.
type QAChatProps = QAChatScope & { fillHeight?: boolean };

interface QACitation {
  source_type: string;
  source_id: string;
  source_title?: string;
  text_excerpt: string;
  timestamp?: number;
  page?: number;
  // Extras spread from backend citation metadata. Present for
  // transcript_segment citations so we can link to the meeting.
  meeting_id?: string;
  start_time?: number;
  chunk_id?: string;
}

interface QAEntry {
  question: string;
  answer: string;
  citations: QACitation[];
  grounding_score?: number;
}

// Build the navigation target for a citation. Transcript segments go to the
// meeting page with the segment's start_time as a hash so the transcript can
// auto-scroll; documents currently just link to the meeting for now. Returns
// null when we don't have enough info to link (keep it as plain text).
function citationHref(
  c: QACitation,
  dealId: string | undefined,
): string | null {
  if (!dealId) return null;
  if (c.source_type === "transcript_segment" && c.meeting_id) {
    const frag = c.start_time != null ? `#t=${c.start_time}` : "";
    return `/deals/${dealId}/meetings/${c.meeting_id}${frag}`;
  }
  return null;
}

// Replace ``[Source:chunk_N]`` tokens in the answer text with clickable
// <Link>s (when the Nth citation has a target) or keep them as plain text
// when we can't build a link. Fragments are stitched back into the final
// React children array so whitespace / paragraph breaks survive.
function renderAnswerWithCitations(
  answer: string,
  citations: QACitation[],
  dealId: string | undefined,
): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  const regex = /\[Source:([a-z0-9_-]+)\]/gi;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let keyIdx = 0;
  while ((match = regex.exec(answer)) !== null) {
    if (match.index > lastIndex) {
      parts.push(answer.slice(lastIndex, match.index));
    }
    const chunkId = match[1];
    // chunk_id is "chunk_<N>" where N indexes into the citations array.
    const n = Number(chunkId.replace(/^chunk_/, ""));
    const c = Number.isFinite(n) ? citations[n] : undefined;
    const href = c ? citationHref(c, dealId) : null;
    const label = c?.source_title || `source ${Number.isFinite(n) ? n + 1 : "?"}`;
    parts.push(
      href ? (
        <Link
          key={`c-${keyIdx++}`}
          href={href}
          className="text-primary underline decoration-dotted underline-offset-2 hover:decoration-solid"
          title={c?.text_excerpt}
        >
          [{label}]
        </Link>
      ) : (
        <span key={`c-${keyIdx++}`} className="text-muted-foreground">
          [{label}]
        </span>
      ),
    );
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < answer.length) parts.push(answer.slice(lastIndex));
  return parts;
}

const DEAL_EXAMPLES = [
  "What are the key financial metrics discussed?",
  "What risks were identified in the due diligence?",
  "Summarize the management team's growth strategy",
];

const MEETING_EXAMPLES = [
  "What were the key takeaways from this meeting?",
  "What action items were discussed?",
  "Summarize the financial metrics mentioned",
];

export function QAChat(props: QAChatProps) {
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState<QAEntry[]>([]);
  const dealMutation = useAskQuestion();
  const meetingMutation = useMeetingAskQuestion();
  const askQuestion = props.scope === "deal" ? dealMutation : meetingMutation;
  const dealId =
    props.scope === "deal" ? props.dealId : props.dealId;
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [history]);

  const examples = props.scope === "deal" ? DEAL_EXAMPLES : MEETING_EXAMPLES;
  const intro =
    props.scope === "deal"
      ? "Questions are answered using meeting transcripts and documents from this deal, with source citations."
      : "Questions are answered using the transcript and analysis from this meeting, with source citations.";
  const placeholder =
    props.scope === "deal"
      ? "Ask a question about this deal..."
      : "Ask a question about this meeting...";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || askQuestion.isPending) return;

    const q = question.trim();
    setQuestion("");

    try {
      const response =
        props.scope === "deal"
          ? await dealMutation.mutateAsync({
              dealId: props.dealId,
              payload: { question: q },
            })
          : await meetingMutation.mutateAsync({
              meetingId: props.meetingId,
              payload: { question: q },
            });
      setHistory((prev) => [
        ...prev,
        {
          question: q,
          answer: response.answer,
          citations: response.citations,
          grounding_score: response.grounding_score,
        },
      ]);
    } catch (err: unknown) {
      // Surface the backend detail when present (e.g. Fireworks 412 "Account
      // suspended"), so a billing / config issue isn't hidden behind a
      // generic "Sorry, an error occurred" message.
      let detail = "";
      if (err && typeof err === "object" && "response" in err) {
        const r = (err as { response?: { data?: { detail?: string } } })
          .response;
        detail = r?.data?.detail ?? "";
      }
      const answer = detail
        ? `Sorry, the model couldn't answer: ${detail}`
        : "Sorry, an error occurred while processing your question.";
      setHistory((prev) => [
        ...prev,
        { question: q, answer, citations: [] },
      ]);
    }
  };

  const fillHeight = props.fillHeight;
  return (
    <div
      className={
        "flex flex-col rounded-lg border bg-white" +
        (fillHeight ? " h-full" : "")
      }
    >
      <div
        className={
          "overflow-y-auto p-4 space-y-6" +
          (fillHeight
            ? " flex-1 min-h-0"
            : " min-h-[400px] max-h-[600px]")
        }
      >
        {history.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <MessageCircle className="h-12 w-12 text-muted-foreground/30" />
            <h3 className="mt-4 text-lg font-medium">Ask a question</h3>
            <p className="mt-1 max-w-sm text-sm text-muted-foreground">
              {intro}
            </p>
            <div className="mt-6 space-y-2">
              <p className="text-xs font-medium text-muted-foreground">
                Example questions:
              </p>
              {examples.map((example) => (
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
              <div className="flex justify-end">
                <div className="max-w-[80%] rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground">
                  {entry.question}
                </div>
              </div>
              <div className="space-y-2">
                <div className="max-w-[90%] rounded-lg bg-muted px-4 py-3 text-sm">
                  <p className="whitespace-pre-wrap">
                    {renderAnswerWithCitations(
                      entry.answer,
                      entry.citations,
                      dealId,
                    )}
                  </p>
                </div>
                {entry.citations.length > 0 && (
                  <div className="ml-2 space-y-1">
                    <p className="flex items-center gap-1 text-xs font-medium text-muted-foreground">
                      <BookOpen className="h-3 w-3" />
                      Sources ({entry.citations.length})
                    </p>
                    {entry.citations.map((citation, j) => {
                      const href = citationHref(citation, dealId);
                      const body = (
                        <>
                          <p className="font-medium">
                            {citation.source_title || `Source ${j + 1}`}
                          </p>
                          <p className="mt-0.5 text-muted-foreground line-clamp-2">
                            {citation.text_excerpt}
                          </p>
                        </>
                      );
                      return href ? (
                        <Link
                          key={j}
                          href={href}
                          className="block rounded border bg-white px-3 py-2 text-xs hover:border-primary hover:bg-muted"
                        >
                          {body}
                        </Link>
                      ) : (
                        <div
                          key={j}
                          className="rounded border bg-white px-3 py-2 text-xs"
                        >
                          {body}
                        </div>
                      );
                    })}
                  </div>
                )}
                {entry.grounding_score != null && (
                  <p className="ml-2 text-xs text-muted-foreground">
                    Confidence: {Math.round(entry.grounding_score * 100)}%
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

        <div ref={chatEndRef} />
      </div>

      <form onSubmit={handleSubmit} className="border-t p-4">
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder={placeholder}
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
