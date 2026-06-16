"use client";

// Global AI Chat — workspace redesign mirroring the deal AI Chat tab.
// Adds an extra scope layer over the deal-page version: top of the left
// rail is a deal selector, then meetings within that deal cascade
// underneath. Right pane + floating composer are otherwise identical.

import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowRight, Sparkles } from "lucide-react";
import { useDeals } from "@/hooks/use-deals";
import { useMeetings } from "@/hooks/use-meetings";
import { useAskQuestion, useMeetingAskQuestion } from "@/hooks/use-qa";
import { ApiError, NetworkError, warmWorker } from "@/lib/worker-api";
import { LoadingState } from "@/components/shared/loading-state";
import { SUGGESTIONS, type ChatMsg, type Scope } from "@/components/chat/types";
import { ScopeRail } from "@/components/chat/scope-rail";
import {
  Bubble,
  ConversationHeader,
  EmptyChat,
} from "@/components/chat/conversation";
import { FloatingComposer } from "@/components/chat/floating-composer";

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

  // Wake the worker on mount so the first QA request doesn't pay the
  // Railway cold-start penalty. Best-effort; failures are silent.
  useEffect(() => {
    warmWorker();
  }, []);

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
      const apiErr = err instanceof ApiError ? err : null;
      // Surface enough to diagnose: HTTP status + server detail when present.
      // Treat edge failures (502/503/504) the same as an unreachable worker —
      // the user-facing root cause is identical (worker not responding), and
      // the diagnostic pointer to NEXT_PUBLIC_API_URL is more useful than a
      // bare HTTP code.
      const workerDown =
        err instanceof NetworkError ||
        (apiErr !== null && [502, 503, 504].includes(apiErr.status));
      const text = workerDown
        ? "Couldn't reach the worker. Check NEXT_PUBLIC_API_URL and that the worker is up."
        : apiErr
          ? `[${apiErr.status}] ${apiErr.message}`
          : (err instanceof Error && err.message) ||
            "Sorry, an error occurred while processing your question.";
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
                suggestions={SUGGESTIONS}
                onPick={(p) => setInput(p)}
              />
            ) : (
              <div className="px-5 py-4 flex flex-col gap-5">
                {messages.map((m) => (
                  <Bubble key={m.id} msg={m} dealId={m.scope.dealId} />
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
