"use client";

// AI Chat tab — workspace redesign of the Q&A surface. Layout matches the
// design's spec: left rail with deal-wide / per-meeting scope selectors,
// right pane with message history, floating composer pinned to the bottom
// with elevated shadow + scope chip + suggested prompts.
//
// Wiring stays on top of the existing useAskQuestion / useMeetingAskQuestion
// hooks so answers stream the same RAG citations as before — only the chrome
// is new.

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import {
  ArrowRight,
  BookOpen,
  Mic,
  MoreHorizontal,
  Plus,
  Search,
  Send,
  Sparkles,
} from "lucide-react";
import { useDeal } from "@/hooks/use-deals";
import { useMeetings } from "@/hooks/use-meetings";
import { useAskQuestion, useMeetingAskQuestion } from "@/hooks/use-qa";
import { PillButton } from "@/components/workspace/primitives";
import { LoadingState } from "@/components/shared/loading-state";
import type { Meeting, Citation } from "@/types";

type Scope =
  | { kind: "deal" }
  | { kind: "meeting"; meetingId: string };

interface ChatMsg {
  id: string;
  role: "user" | "ai";
  text: string;
  citations?: Citation[];
  pending?: boolean;
  scope: Scope;
  groundingScore?: number;
}

const SUGGESTIONS = [
  "Summarize the last 5 meetings",
  "What action items are due this week?",
  "Which questions came up but never got answered?",
  "Compare what management said vs the CFO",
  "Draft an IC pre-read from this week's calls",
];

function citationHref(c: Citation, dealId: string): string | null {
  type CWithMeta = Citation & { meeting_id?: string; start_time?: number };
  const cm = c as CWithMeta;
  if (c.source_type === "transcript_segment" && cm.meeting_id) {
    const frag = cm.start_time != null ? `#t=${cm.start_time}` : "";
    return `/deals/${dealId}/meetings/${cm.meeting_id}${frag}`;
  }
  return null;
}

export default function ChatPage() {
  const params = useParams<{ dealId: string }>();
  const searchParams = useSearchParams();
  const dealId = params.dealId;

  const { data: deal } = useDeal(dealId);
  const { data: meetingsResp } = useMeetings(dealId);
  const meetings = meetingsResp?.items ?? [];

  const [scope, setScope] = useState<Scope>({ kind: "deal" });
  const [messages, setMessages] = useState<ChatMsg[]>([]);
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

    const userMsg: ChatMsg = {
      id: `u-${Date.now()}`,
      role: "user",
      text: q,
      scope,
    };
    const aiMsg: ChatMsg = {
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
          : await meetingAsk.mutateAsync({
              meetingId: scope.meetingId,
              payload: { question: q },
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
      let detail = "";
      if (err && typeof err === "object" && "response" in err) {
        const r = (err as { response?: { data?: { detail?: string } } })
          .response;
        detail = r?.data?.detail ?? "";
      }
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

function ScopeRail({
  meetings,
  scope,
  onScope,
  search,
  onSearch,
  dealName,
}: {
  meetings: Meeting[];
  scope: Scope;
  onScope: (s: Scope) => void;
  search: string;
  onSearch: (v: string) => void;
  dealName: string;
}) {
  const dealActive = scope.kind === "deal";
  return (
    <aside
      className="ws-card overflow-hidden flex flex-col self-start lg:sticky lg:top-3"
      style={{ maxHeight: "calc(100vh - 100px)" }}
    >
      <div className="ws-card-header" style={{ background: "var(--ws-surface)" }}>
        <span className="ws-eyebrow">Scope</span>
        <div className="flex-1" />
        <PillButton>
          <Plus className="w-3 h-3" /> New
        </PillButton>
      </div>
      <button
        type="button"
        onClick={() => onScope({ kind: "deal" })}
        className="grid grid-cols-[auto_1fr] gap-2.5 items-center px-3.5 py-2.5 cursor-pointer text-left"
        style={{
          background: dealActive ? "var(--ws-ai-tint)" : "transparent",
          borderLeft: `2px solid ${dealActive ? "var(--ws-ai-ink)" : "transparent"}`,
          borderBottom: "1px solid var(--ws-border)",
        }}
      >
        <Sparkles
          className="w-4 h-4"
          style={{ color: dealActive ? "var(--ws-ai-ink)" : "var(--ws-muted)" }}
        />
        <div>
          <div
            className="text-[13px] font-semibold"
            style={{ color: "var(--ws-ink)" }}
          >
            {dealName}
          </div>
          <div className="text-[11px]" style={{ color: "var(--ws-muted)" }}>
            All meetings & documents
          </div>
        </div>
      </button>
      <div
        className="px-3 py-2 flex items-center gap-1.5 text-[12px]"
        style={{
          borderBottom: "1px solid var(--ws-border)",
          background: "var(--ws-bg)",
          color: "var(--ws-muted)",
        }}
      >
        <Search className="w-3 h-3" />
        <input
          value={search}
          onChange={(e) => onSearch(e.target.value)}
          placeholder="Filter meetings…"
          className="flex-1 bg-transparent outline-none border-none"
          style={{ color: "var(--ws-ink2)" }}
        />
      </div>
      <div className="flex-1 overflow-y-auto">
        {meetings.length === 0 ? (
          <div className="px-3.5 py-3 text-[11.5px]" style={{ color: "var(--ws-faint)" }}>
            No meetings to scope to.
          </div>
        ) : (
          meetings.map((m, i) => {
            const active = scope.kind === "meeting" && scope.meetingId === m.id;
            const d = m.meeting_date
              ? new Date(m.meeting_date)
              : new Date(m.created_at);
            return (
              <button
                key={m.id}
                type="button"
                onClick={() => onScope({ kind: "meeting", meetingId: m.id })}
                className="w-full grid grid-cols-[auto_1fr] gap-2.5 items-start px-3.5 py-2 text-left cursor-pointer"
                style={{
                  background: active ? "var(--ws-ai-tint)" : "transparent",
                  borderLeft: `2px solid ${active ? "var(--ws-ai-ink)" : "transparent"}`,
                  borderTop: i > 0 ? "1px solid var(--ws-border)" : undefined,
                }}
              >
                <Mic
                  className="w-3 h-3 mt-0.5 shrink-0"
                  style={{ color: active ? "var(--ws-ai-ink)" : "var(--ws-faint)" }}
                />
                <div className="min-w-0">
                  <div
                    className="text-[12px] font-semibold truncate"
                    style={{ color: "var(--ws-ink)" }}
                  >
                    {m.title}
                  </div>
                  <div
                    className="text-[10.5px] mt-0.5 ws-mono"
                    style={{ color: "var(--ws-muted)" }}
                  >
                    {d.toLocaleDateString(undefined, {
                      month: "short",
                      day: "numeric",
                    })}
                  </div>
                </div>
              </button>
            );
          })
        )}
      </div>
    </aside>
  );
}

function ConversationHeader({
  scope,
  dealName,
  scopedMeeting,
}: {
  scope: Scope;
  dealName: string;
  scopedMeeting: Meeting | null;
}) {
  return (
    <div className="flex items-center gap-2 flex-wrap">
      <h2 className="m-0 text-[16px] font-semibold" style={{ color: "var(--ws-ink)" }}>
        Ask Cogni
      </h2>
      <span
        className="text-[11.5px] inline-flex items-center gap-1.5"
        style={{ color: "var(--ws-muted)" }}
      >
        <span
          className="px-1.5 py-px rounded"
          style={{
            background: "var(--ws-ai-tint)",
            color: "var(--ws-ai-ink)",
            fontWeight: 600,
            fontSize: 10.5,
          }}
        >
          {scope.kind === "deal" ? dealName : (scopedMeeting?.title ?? "Meeting")}
        </span>
        {scope.kind === "deal" ? (
          <span>· deal-wide context</span>
        ) : (
          <span>· single meeting</span>
        )}
      </span>
      <div className="flex-1" />
      <PillButton>
        <MoreHorizontal className="w-3 h-3" />
      </PillButton>
    </div>
  );
}

function EmptyChat({
  dealName,
  onPick,
}: {
  dealName: string;
  onPick: (p: string) => void;
}) {
  return (
    <div className="flex flex-col items-center text-center px-5 py-10 gap-2.5">
      <span
        className="w-[36px] h-[36px] rounded-md grid place-items-center"
        style={{
          background: "linear-gradient(135deg, var(--ws-accent), var(--ws-ai-ink))",
          color: "#fff",
        }}
      >
        <Sparkles className="w-4 h-4" />
      </span>
      <h3
        className="m-0 text-[16px] font-semibold tracking-tight"
        style={{ color: "var(--ws-ink)" }}
      >
        Ask anything about {dealName}
      </h3>
      <p
        className="m-0 max-w-[420px] text-[12.5px]"
        style={{ color: "var(--ws-muted)" }}
      >
        Answers are grounded in meeting transcripts and uploaded documents,
        with citations you can click to jump back to the source segment.
      </p>
      <div className="flex flex-col gap-1.5 mt-2 w-full max-w-md">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => onPick(s)}
            className="px-3 py-2 text-left rounded-md text-[12px]"
            style={{
              background: "var(--ws-bg)",
              border: "1px dashed var(--ws-border-strong)",
              color: "var(--ws-ink2)",
            }}
          >
            <Sparkles
              className="w-3 h-3 inline align-middle mr-1.5"
              style={{ color: "var(--ws-ai-ink)" }}
            />
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}

function Bubble({ msg, dealId }: { msg: ChatMsg; dealId: string }) {
  if (msg.role === "user") {
    return (
      <div className="flex justify-end">
        <div
          className="max-w-[80%] rounded-[10px] px-3.5 py-2 text-[13px] leading-relaxed"
          style={{ background: "var(--ws-ink)", color: "#fff" }}
        >
          {msg.text}
        </div>
      </div>
    );
  }
  return (
    <div className="flex gap-2.5 items-start">
      <span
        className="w-[28px] h-[28px] rounded-md grid place-items-center shrink-0 mt-0.5"
        style={{
          background: "linear-gradient(135deg, var(--ws-accent), var(--ws-ai-ink))",
          color: "#fff",
        }}
      >
        <Sparkles className="w-3 h-3" />
      </span>
      <div className="flex-1 min-w-0">
        {msg.pending ? (
          <LoadingState message="Thinking…" />
        ) : (
          <>
            <div
              className="rounded-[10px] px-3.5 py-2.5 text-[13px] leading-relaxed whitespace-pre-wrap"
              style={{
                background: "var(--ws-bg)",
                border: "1px solid var(--ws-border)",
                color: "var(--ws-ink2)",
              }}
            >
              {msg.text}
            </div>
            {msg.citations && msg.citations.length > 0 && (
              <div className="flex flex-col gap-1.5 mt-2 ml-2">
                <p
                  className="flex items-center gap-1 text-[11px] font-semibold m-0"
                  style={{ color: "var(--ws-muted)" }}
                >
                  <BookOpen className="w-3 h-3" />
                  Sources ({msg.citations.length})
                </p>
                {msg.citations.map((c, i) => {
                  const href = citationHref(c, dealId);
                  const inner = (
                    <>
                      <p
                        className="m-0 text-[11.5px] font-semibold"
                        style={{ color: "var(--ws-ink)" }}
                      >
                        {c.source_title || `Source ${i + 1}`}
                      </p>
                      <p
                        className="m-0 mt-0.5 text-[11px] line-clamp-2"
                        style={{ color: "var(--ws-muted)" }}
                      >
                        {c.text_excerpt}
                      </p>
                    </>
                  );
                  return href ? (
                    <Link
                      key={i}
                      href={href}
                      className="block rounded-md px-2.5 py-1.5"
                      style={{
                        background: "var(--ws-bg)",
                        border: "1px solid var(--ws-border)",
                      }}
                    >
                      {inner}
                    </Link>
                  ) : (
                    <div
                      key={i}
                      className="rounded-md px-2.5 py-1.5"
                      style={{
                        background: "var(--ws-bg)",
                        border: "1px solid var(--ws-border)",
                      }}
                    >
                      {inner}
                    </div>
                  );
                })}
              </div>
            )}
            {msg.groundingScore != null && (
              <p
                className="ml-2 mt-1 text-[10.5px]"
                style={{ color: "var(--ws-muted)" }}
              >
                Confidence {Math.round(msg.groundingScore * 100)}%
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function FloatingComposer({
  input,
  onInput,
  scope,
  scopedMeeting,
  dealName,
  onClearScope,
  onSubmit,
  disabled,
  suggestions,
  onPick,
}: {
  input: string;
  onInput: (v: string) => void;
  scope: Scope;
  scopedMeeting: Meeting | null;
  dealName: string;
  onClearScope: () => void;
  onSubmit: (e: React.FormEvent) => void;
  disabled: boolean;
  suggestions: string[];
  onPick: (p: string) => void;
}) {
  return (
    <div
      className="fixed bottom-0 left-0 right-0 px-7 pb-5 pointer-events-none"
      style={{ zIndex: 30 }}
    >
      <div className="max-w-7xl mx-auto pointer-events-auto">
        {suggestions.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-2 justify-center">
            {suggestions.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => onPick(s)}
                className="px-2.5 py-1 rounded-full text-[11.5px]"
                style={{
                  background: "var(--ws-bg)",
                  border: "1px solid var(--ws-border)",
                  color: "var(--ws-ink2)",
                  boxShadow: "0 4px 12px rgba(0,0,0,0.04)",
                }}
              >
                <Sparkles
                  className="w-2.5 h-2.5 inline align-middle mr-1"
                  style={{ color: "var(--ws-ai-ink)" }}
                />
                {s}
              </button>
            ))}
          </div>
        )}
        <form
          onSubmit={onSubmit}
          className="flex items-center gap-2 rounded-[10px] px-3 py-2"
          style={{
            background: "var(--ws-bg)",
            border: "1px solid var(--ws-border-strong)",
            boxShadow: "0 8px 24px rgba(0, 0, 0, 0.08)",
          }}
        >
          <span
            className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10.5px] font-semibold whitespace-nowrap shrink-0"
            style={{
              background: "var(--ws-ai-tint)",
              color: "var(--ws-ai-ink)",
            }}
            title={scope.kind === "deal" ? dealName : scopedMeeting?.title}
          >
            {scope.kind === "deal" ? (
              <>
                <Sparkles className="w-2.5 h-2.5" /> Deal-wide
              </>
            ) : (
              <>
                <Mic className="w-2.5 h-2.5" />
                <span className="max-w-[120px] truncate">
                  {scopedMeeting?.title ?? "Meeting"}
                </span>
                <button
                  type="button"
                  onClick={onClearScope}
                  className="ml-0.5"
                  style={{ color: "var(--ws-ai-ink)" }}
                >
                  ×
                </button>
              </>
            )}
          </span>
          <input
            value={input}
            onChange={(e) => onInput(e.target.value)}
            placeholder={
              scope.kind === "deal"
                ? `Ask anything about ${dealName}…`
                : `Ask about this meeting…`
            }
            className="flex-1 bg-transparent outline-none border-none text-[13px]"
            style={{ color: "var(--ws-ink)" }}
            disabled={disabled}
          />
          <button
            type="submit"
            disabled={disabled || !input.trim()}
            className="w-[32px] h-[32px] rounded-md grid place-items-center disabled:opacity-50"
            style={{
              background: "var(--ws-ink)",
              color: "#fff",
              border: "none",
            }}
          >
            {disabled ? (
              <ArrowRight className="w-3.5 h-3.5 animate-pulse" />
            ) : (
              <Send className="w-3.5 h-3.5" />
            )}
          </button>
        </form>
      </div>
    </div>
  );
}

