"use client";

// AI Chat tab — workspace redesign of the Q&A surface. Left rail with
// deal-wide / per-meeting scope selectors, right pane with message history,
// floating composer pinned to the bottom. The message bubble + empty state
// are shared with the global chat page; the QA-specific chrome lives in
// components/qa/chat-chrome.tsx.
//
// Wiring stays on top of the existing useAskQuestion / useMeetingAskQuestion
// hooks so answers carry the same RAG citations as before.

import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { useDeal } from "@/hooks/use-deals";
import { useMeetings } from "@/hooks/use-meetings";
import { useAskQuestion, useMeetingAskQuestion } from "@/hooks/use-qa";
import { ApiError, NetworkError } from "@/lib/worker-api";
import { Bubble, EmptyChat } from "@/components/chat/conversation";
import {
  ConversationHeader,
  FloatingComposer,
  ScopeRail,
  type QaChatMsg,
  type Scope,
} from "@/components/qa/chat-chrome";

const SUGGESTIONS = [
  "Summarize the last 5 meetings",
  "What action items are due this week?",
  "Which questions came up but never got answered?",
  "Compare what management said vs the CFO",
  "Draft an IC pre-read from this week's calls",
];

export default function ChatPage() {
  const params = useParams<{ dealId: string }>();
  const searchParams = useSearchParams();
  const dealId = params.dealId;

  const { data: deal } = useDeal(dealId);
  const { data: meetingsResp } = useMeetings(dealId);
  const meetings = meetingsResp?.items ?? [];

  const [scope, setScope] = useState<Scope>({ kind: "deal" });
  const [messages, setMessages] = useState<QaChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [search, setSearch] = useState("");
  const dealAsk = useAskQuestion();
  const meetingAsk = useMeetingAskQuestion();
  const isPending = dealAsk.isPending || meetingAsk.isPending;
  const scrollRef = useRef<HTMLDivElement>(null);

  // Prefill question from `?q=` so links from Overview / Action Items
  // jump straight into the right pane.
  useEffect(() => {
    const q = searchParams.get("q");
    if (q) setInput(q);
  }, [searchParams]);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  const filteredMeetings = useMemo(() => {
    if (!search.trim()) return meetings;
    const s = search.toLowerCase();
    return meetings.filter((m) => m.title.toLowerCase().includes(s));
  }, [meetings, search]);

  const scopedMeeting = scope.kind === "meeting"
    ? meetings.find((m) => m.id === scope.meetingId)
    : null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const q = input.trim();
    if (!q || isPending) return;
    setInput("");

    const userMsg: QaChatMsg = {
      id: `u-${Date.now()}`,
      role: "user",
      text: q,
      scope,
    };
    const aiMsg: QaChatMsg = {
      id: `a-${Date.now()}`,
      role: "ai",
      text: "",
      pending: true,
      scope,
    };
    setMessages((prev) => [...prev, userMsg, aiMsg]);

    try {
      const response =
        scope.kind === "deal"
          ? await dealAsk.mutateAsync({
              dealId,
              payload: { question: q },
            })
          : scope.kind === "meeting"
            ? await meetingAsk.mutateAsync({
                meetingId: scope.meetingId,
                payload: { question: q },
              })
            : await dealAsk.mutateAsync({
                dealId,
                payload: { question: q, meeting_ids: scope.meetingIds },
              });
      setMessages((prev) =>
        prev.map((m) =>
          m.id === aiMsg.id
            ? {
                ...m,
                text: response.answer,
                citations: response.citations,
                groundingScore: response.grounding_score,
                pending: false,
              }
            : m,
        ),
      );
    } catch (err: unknown) {
      const workerDown =
        err instanceof NetworkError ||
        (err instanceof ApiError && [502, 503, 504].includes(err.status));
      const detail = workerDown
        ? "Couldn't reach the worker."
        : err instanceof ApiError
          ? err.message
          : "";
      setMessages((prev) =>
        prev.map((m) =>
          m.id === aiMsg.id
            ? {
                ...m,
                pending: false,
                text: detail
                  ? `Sorry, the model couldn't answer: ${detail}`
                  : "Sorry, an error occurred while processing your question.",
              }
            : m,
        ),
      );
    }
  };

  return (
    <div
      className="grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-3.5 px-7 pt-4 pb-32"
      style={{ background: "var(--ws-sub)", minHeight: "100%" }}
    >
      <ScopeRail
        meetings={filteredMeetings}
        scope={scope}
        onScope={setScope}
        search={search}
        onSearch={setSearch}
        dealName={deal?.name ?? "this deal"}
      />

      <div className="min-w-0 flex flex-col gap-3">
        <ConversationHeader
          scope={scope}
          dealName={deal?.name ?? "Deal"}
          scopedMeeting={scopedMeeting ?? null}
        />

        <div
          ref={scrollRef}
          className="ws-card flex-1 overflow-y-auto"
          style={{ minHeight: 360, maxHeight: "calc(100vh - 380px)" }}
        >
          {messages.length === 0 ? (
            <EmptyChat
              dealName={deal?.name ?? "this deal"}
              suggestions={SUGGESTIONS}
              onPick={(p) => setInput(p)}
            />
          ) : (
            <div className="px-5 py-4 flex flex-col gap-5">
              {messages.map((m) => (
                <Bubble key={m.id} msg={m} dealId={dealId} />
              ))}
            </div>
          )}
        </div>
      </div>

      <FloatingComposer
        input={input}
        onInput={setInput}
        scope={scope}
        scopedMeeting={scopedMeeting ?? null}
        dealName={deal?.name ?? "this deal"}
        onClearScope={() => setScope({ kind: "deal" })}
        onSubmit={handleSubmit}
        disabled={isPending}
        suggestions={messages.length === 0 ? SUGGESTIONS.slice(0, 3) : []}
        onPick={(p) => setInput(p)}
      />
    </div>
  );
}
