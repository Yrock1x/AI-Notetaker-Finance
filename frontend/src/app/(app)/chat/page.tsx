"use client";

// Global AI Chat — workspace redesign mirroring the deal AI Chat tab.
// Adds an extra scope layer over the deal-page version: top of the left
// rail is a deal selector, then meetings within that deal cascade
// underneath. Right pane + floating composer are otherwise identical.

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowRight,
  BookOpen,
  Briefcase,
  ChevronDown,
  ChevronRight,
  Mic,
  Search,
  Send,
  Sparkles,
} from "lucide-react";
import { useDeals } from "@/hooks/use-deals";
import { useMeetings } from "@/hooks/use-meetings";
import { useAskQuestion, useMeetingAskQuestion } from "@/hooks/use-qa";
import { LoadingState } from "@/components/shared/loading-state";
import type { Citation, Deal, Meeting } from "@/types";

type Scope =
  | { kind: "deal"; dealId: string }
  | { kind: "meeting"; dealId: string; meetingId: string };

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
  "Summarize this deal's last 5 meetings",
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
  return (
    <Suspense fallback={<LoadingState message="Loading…" />}>
      <ChatContent />
    </Suspense>
  );
}

function ChatContent() {
  const router = useRouter();
  const search = useSearchParams();
  const { data: dealsResp, isLoading: dealsLoading } = useDeals();
  const deals = dealsResp?.items ?? [];

  const initialDealId = search.get("deal") ?? "";
  const initialMeetingId = search.get("meeting") ?? "";
  const initialQ = search.get("q") ?? "";

  const [scope, setScope] = useState<Scope | null>(
    initialDealId
      ? initialMeetingId
        ? { kind: "meeting", dealId: initialDealId, meetingId: initialMeetingId }
        : { kind: "deal", dealId: initialDealId }
      : null,
  );
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState(initialQ);
  const [railSearch, setRailSearch] = useState("");
  const dealAsk = useAskQuestion();
  const meetingAsk = useMeetingAskQuestion();
  const isPending = dealAsk.isPending || meetingAsk.isPending;
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-select first deal when none chosen.
  useEffect(() => {
    if (!scope && deals.length > 0) {
      setScope({ kind: "deal", dealId: deals[0].id });
    }
  }, [deals, scope]);

  // Sync URL so the scope is shareable + survives refresh.
  useEffect(() => {
    if (!scope) return;
    const params = new URLSearchParams();
    params.set("deal", scope.dealId);
    if (scope.kind === "meeting") params.set("meeting", scope.meetingId);
    router.replace(`/chat?${params.toString()}`, { scroll: false });
  }, [scope, router]);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  const activeDeal = scope ? deals.find((d) => d.id === scope.dealId) : null;
  const { data: meetingsResp } = useMeetings(scope?.dealId);
  const meetings = meetingsResp?.items ?? [];
  const activeMeeting =
    scope?.kind === "meeting"
      ? meetings.find((m) => m.id === scope.meetingId) ?? null
      : null;

  // Drop the meeting filter if we switched deals and the meeting is no
  // longer in the active deal.
  useEffect(() => {
    if (scope?.kind !== "meeting") return;
    if (meetings.length > 0 && !meetings.some((m) => m.id === scope.meetingId)) {
      setScope({ kind: "deal", dealId: scope.dealId });
    }
  }, [scope, meetings]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const q = input.trim();
    if (!q || isPending || !scope) return;
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
              dealId: scope.dealId,
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
      let status: number | undefined;
      let code: string | undefined;
      let message = "";
      if (err && typeof err === "object") {
        const e = err as {
          response?: { status?: number; data?: { detail?: string } };
          code?: string;
          message?: string;
        };
        status = e.response?.status;
        detail = e.response?.data?.detail ?? "";
        code = e.code;
        message = e.message ?? "";
      }
      // Surface enough to diagnose: HTTP status + server detail when present,
      // otherwise fall back to the axios error code/message (network errors,
      // CORS, missing NEXT_PUBLIC_API_URL all land here).
      const text = detail
        ? `${status ? `[${status}] ` : ""}${detail}`
        : status
          ? `Request failed with HTTP ${status}.`
          : code === "ERR_NETWORK"
            ? "Couldn't reach the worker. Check NEXT_PUBLIC_API_URL and that the worker is up."
            : message || "Sorry, an error occurred while processing your question.";
      setMessages((prev) =>
        prev.map((m) =>
          m.id === aiMsg.id
            ? {
                ...m,
                pending: false,
                text: `⚠️ ${text}`,
              }
            : m,
        ),
      );
    }
  };

  if (dealsLoading) {
    return <LoadingState message="Loading deals…" />;
  }

  if (deals.length === 0) {
    return (
      <div
        data-workspace
        className="-m-8 md:-m-10 min-h-full"
        style={{ background: "var(--ws-sub)" }}
      >
        <div className="px-7 pt-10 pb-32 max-w-2xl mx-auto text-center">
          <span
            className="inline-flex items-center justify-center w-[40px] h-[40px] rounded-md mx-auto"
            style={{
              background: "linear-gradient(135deg, var(--ws-accent), var(--ws-ai-ink))",
              color: "#fff",
            }}
          >
            <Sparkles className="w-5 h-5" />
          </span>
          <h1
            className="mt-3 text-[20px] font-semibold tracking-tight"
            style={{ color: "var(--ws-ink)" }}
          >
            Ask Cogni
          </h1>
          <p
            className="mt-2 text-[13px]"
            style={{ color: "var(--ws-muted)" }}
          >
            Create a deal and add a meeting or document to start asking
            questions across your deal corpus.
          </p>
          <Link
            href="/deals/new"
            className="inline-flex items-center gap-1.5 mt-4 px-3 py-2 rounded-md text-[12px] font-semibold"
            style={{
              background: "var(--ws-ink)",
              color: "#fff",
            }}
          >
            Create a deal <ArrowRight className="w-3 h-3" />
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div
      data-workspace
      className="-m-8 md:-m-10 min-h-full"
    >
      <div
        className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-3.5 px-7 pt-4 pb-32"
        style={{ background: "var(--ws-sub)", minHeight: "100%" }}
      >
        <ScopeRail
          deals={deals}
          meetings={meetings}
          scope={scope}
          onScope={setScope}
          search={railSearch}
          onSearch={setRailSearch}
        />

        <div className="min-w-0 flex flex-col gap-3">
          <ConversationHeader
            scope={scope}
            activeDeal={activeDeal ?? null}
            activeMeeting={activeMeeting}
          />

          <div
            ref={scrollRef}
            className="ws-card flex-1 overflow-y-auto"
            style={{ minHeight: 360, maxHeight: "calc(100vh - 380px)" }}
          >
            {messages.length === 0 ? (
              <EmptyChat
                dealName={activeDeal?.name ?? "your deal"}
                onPick={(p) => setInput(p)}
              />
            ) : (
              <div className="px-5 py-4 flex flex-col gap-5">
                {messages.map((m) => (
                  <Bubble key={m.id} msg={m} />
                ))}
              </div>
            )}
          </div>
        </div>

        <FloatingComposer
          input={input}
          onInput={setInput}
          scope={scope}
          activeDeal={activeDeal ?? null}
          activeMeeting={activeMeeting}
          onClearMeetingScope={() =>
            scope?.kind === "meeting"
              ? setScope({ kind: "deal", dealId: scope.dealId })
              : undefined
          }
          onSubmit={handleSubmit}
          disabled={isPending || !scope}
          suggestions={messages.length === 0 ? SUGGESTIONS.slice(0, 3) : []}
          onPick={(p) => setInput(p)}
        />
      </div>
    </div>
  );
}

function ScopeRail({
  deals,
  meetings,
  scope,
  onScope,
  search,
  onSearch,
}: {
  deals: Deal[];
  meetings: Meeting[];
  scope: Scope | null;
  onScope: (s: Scope) => void;
  search: string;
  onSearch: (v: string) => void;
}) {
  const [dealsOpen, setDealsOpen] = useState(true);
  const [meetingsOpen, setMeetingsOpen] = useState(true);
  const filteredDeals = useMemo(() => {
    if (!search.trim()) return deals;
    const s = search.toLowerCase();
    return deals.filter(
      (d) =>
        d.name.toLowerCase().includes(s) ||
        (d.target_company ?? "").toLowerCase().includes(s),
    );
  }, [deals, search]);
  const filteredMeetings = useMemo(() => {
    if (!search.trim()) return meetings;
    const s = search.toLowerCase();
    return meetings.filter((m) => m.title.toLowerCase().includes(s));
  }, [meetings, search]);

  return (
    <aside
      className="ws-card overflow-hidden flex flex-col self-start lg:sticky lg:top-3"
      style={{ maxHeight: "calc(100vh - 100px)" }}
    >
      <div
        className="ws-card-header"
        style={{ background: "var(--ws-surface)" }}
      >
        <span className="ws-eyebrow">Scope</span>
      </div>
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
          placeholder="Filter deals or meetings…"
          className="flex-1 bg-transparent outline-none border-none"
          style={{ color: "var(--ws-ink2)" }}
        />
      </div>
      <div className="flex-1 overflow-y-auto">
        <button
          type="button"
          onClick={() => setDealsOpen((v) => !v)}
          className="w-full flex items-center gap-1.5 px-3.5 py-2"
          style={{
            background: "var(--ws-surface)",
            borderBottom: "1px solid var(--ws-border)",
            color: "var(--ws-muted)",
          }}
        >
          {dealsOpen ? (
            <ChevronDown className="w-3 h-3" />
          ) : (
            <ChevronRight className="w-3 h-3" />
          )}
          <span className="ws-eyebrow">Deals · {filteredDeals.length}</span>
        </button>
        {dealsOpen &&
          filteredDeals.map((d, i) => {
            const active = scope?.dealId === d.id && scope?.kind === "deal";
            return (
              <button
                key={d.id}
                type="button"
                onClick={() => onScope({ kind: "deal", dealId: d.id })}
                className="w-full grid grid-cols-[auto_1fr] gap-2.5 items-center px-3.5 py-2 text-left cursor-pointer"
                style={{
                  background: active ? "var(--ws-ai-tint)" : "transparent",
                  borderLeft: `2px solid ${active ? "var(--ws-ai-ink)" : "transparent"}`,
                  borderTop: i > 0 ? "1px solid var(--ws-border)" : undefined,
                }}
              >
                <Briefcase
                  className="w-3 h-3"
                  style={{
                    color: active ? "var(--ws-ai-ink)" : "var(--ws-faint)",
                  }}
                />
                <div className="min-w-0">
                  <div
                    className="text-[12.5px] font-semibold truncate"
                    style={{ color: "var(--ws-ink)" }}
                  >
                    {d.name}
                  </div>
                  {d.target_company && (
                    <div
                      className="text-[10.5px] truncate"
                      style={{ color: "var(--ws-muted)" }}
                    >
                      {d.target_company}
                    </div>
                  )}
                </div>
              </button>
            );
          })}

        {scope && (
          <>
            <button
              type="button"
              onClick={() => setMeetingsOpen((v) => !v)}
              className="w-full flex items-center gap-1.5 px-3.5 py-2 mt-1"
              style={{
                background: "var(--ws-surface)",
                borderTop: "1px solid var(--ws-border)",
                borderBottom: "1px solid var(--ws-border)",
                color: "var(--ws-muted)",
              }}
            >
              {meetingsOpen ? (
                <ChevronDown className="w-3 h-3" />
              ) : (
                <ChevronRight className="w-3 h-3" />
              )}
              <span className="ws-eyebrow">
                Meetings · {filteredMeetings.length}
              </span>
            </button>
            {meetingsOpen && filteredMeetings.length === 0 && (
              <div
                className="px-3.5 py-3 text-[11.5px]"
                style={{ color: "var(--ws-faint)" }}
              >
                No meetings in this deal yet.
              </div>
            )}
            {meetingsOpen &&
              filteredMeetings.map((m, i) => {
                const active =
                  scope.kind === "meeting" && scope.meetingId === m.id;
                const d = m.meeting_date
                  ? new Date(m.meeting_date)
                  : new Date(m.created_at);
                return (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() =>
                      onScope({
                        kind: "meeting",
                        dealId: scope.dealId,
                        meetingId: m.id,
                      })
                    }
                    className="w-full grid grid-cols-[auto_1fr] gap-2.5 items-start px-3.5 py-2 text-left cursor-pointer"
                    style={{
                      background: active ? "var(--ws-ai-tint)" : "transparent",
                      borderLeft: `2px solid ${active ? "var(--ws-ai-ink)" : "transparent"}`,
                      borderTop:
                        i > 0 ? "1px solid var(--ws-border)" : undefined,
                    }}
                  >
                    <Mic
                      className="w-3 h-3 mt-0.5 shrink-0"
                      style={{
                        color: active ? "var(--ws-ai-ink)" : "var(--ws-faint)",
                      }}
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
              })}
          </>
        )}
      </div>
    </aside>
  );
}

function ConversationHeader({
  scope,
  activeDeal,
  activeMeeting,
}: {
  scope: Scope | null;
  activeDeal: Deal | null;
  activeMeeting: Meeting | null;
}) {
  return (
    <div className="flex items-center gap-2 flex-wrap">
      <h2
        className="m-0 text-[16px] font-semibold"
        style={{ color: "var(--ws-ink)" }}
      >
        Ask Cogni
      </h2>
      <span
        className="text-[11.5px] inline-flex items-center gap-1.5"
        style={{ color: "var(--ws-muted)" }}
      >
        {scope ? (
          <>
            <span
              className="px-1.5 py-px rounded"
              style={{
                background: "var(--ws-ai-tint)",
                color: "var(--ws-ai-ink)",
                fontWeight: 600,
                fontSize: 10.5,
              }}
            >
              {scope.kind === "deal"
                ? activeDeal?.name ?? "Deal"
                : activeMeeting?.title ?? "Meeting"}
            </span>
            {scope.kind === "deal" ? (
              <span>· deal-wide context</span>
            ) : (
              <span>· single meeting</span>
            )}
          </>
        ) : (
          <span>Select a deal to begin.</span>
        )}
      </span>
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

function Bubble({ msg }: { msg: ChatMsg }) {
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
                  const href = citationHref(c, msg.scope.dealId);
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
  activeDeal,
  activeMeeting,
  onClearMeetingScope,
  onSubmit,
  disabled,
  suggestions,
  onPick,
}: {
  input: string;
  onInput: (v: string) => void;
  scope: Scope | null;
  activeDeal: Deal | null;
  activeMeeting: Meeting | null;
  onClearMeetingScope: () => void;
  onSubmit: (e: React.FormEvent) => void;
  disabled: boolean;
  suggestions: string[];
  onPick: (p: string) => void;
}) {
  return (
    <div
      className="fixed bottom-0 left-0 lg:left-64 right-0 px-6 pb-5 pointer-events-none"
      style={{ zIndex: 30 }}
    >
      <div className="max-w-5xl mx-auto pointer-events-auto">
        {suggestions.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-2 justify-center">
            {suggestions.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => onPick(s)}
                className="px-3 py-1.5 rounded-full text-[11.5px] bg-white/90 backdrop-blur border border-black/10 text-black/75 shadow-sm transition-colors hover:text-indigo-700 hover:border-indigo-300 hover:bg-indigo-50"
              >
                <Sparkles className="w-2.5 h-2.5 inline align-middle mr-1 text-indigo-600" />
                {s}
              </button>
            ))}
          </div>
        )}
        <div className="relative">
          {/* Halo glow — mirrors the dashboard hero */}
          <div
            aria-hidden
            className="pointer-events-none absolute -inset-px rounded-2xl opacity-60 blur-xl bg-gradient-to-r from-indigo-300/40 via-violet-200/30 to-emerald-300/40"
          />
          <form
            onSubmit={onSubmit}
            className="relative flex items-center gap-2 rounded-2xl px-3 py-2.5 bg-gradient-to-r from-indigo-50/80 via-white to-emerald-50/80 border border-black/[0.08] shadow-[0_12px_32px_rgba(0,0,0,0.08)] backdrop-blur"
          >
            <span
              className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-[10.5px] font-semibold whitespace-nowrap shrink-0 bg-indigo-100 text-indigo-700"
              style={{ maxWidth: 220 }}
              title={
                scope?.kind === "deal"
                  ? activeDeal?.name
                  : activeMeeting?.title
              }
            >
              {scope?.kind === "deal" ? (
                <>
                  <Briefcase className="w-2.5 h-2.5" />
                  <span className="truncate">
                    {activeDeal?.name ?? "Deal"}
                  </span>
                </>
              ) : scope?.kind === "meeting" ? (
                <>
                  <Mic className="w-2.5 h-2.5" />
                  <span className="truncate max-w-[120px]">
                    {activeMeeting?.title ?? "Meeting"}
                  </span>
                  <button
                    type="button"
                    onClick={onClearMeetingScope}
                    className="ml-0.5 text-indigo-700/70 hover:text-indigo-900"
                  >
                    ×
                  </button>
                </>
              ) : (
                <span>No scope</span>
              )}
            </span>
            <input
              value={input}
              onChange={(e) => onInput(e.target.value)}
              placeholder={
                scope
                  ? scope.kind === "deal"
                    ? `Ask anything about ${activeDeal?.name ?? "this deal"}…`
                    : `Ask about this meeting…`
                  : "Select a deal to begin…"
              }
              className="flex-1 bg-transparent outline-none border-none text-[13.5px] placeholder:text-black/35"
              style={{ color: "#0a0a0a" }}
              disabled={disabled}
            />
            <button
              type="submit"
              disabled={disabled || !input.trim()}
              className="inline-flex items-center justify-center h-9 w-9 rounded-full bg-gradient-to-r from-indigo-600 to-violet-600 text-white shadow-sm transition-all hover:from-indigo-500 hover:to-violet-500 hover:shadow-indigo-500/40 hover:shadow-lg disabled:opacity-40 disabled:cursor-not-allowed"
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
    </div>
  );
}
