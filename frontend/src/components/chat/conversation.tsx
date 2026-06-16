"use client";

// Conversation pane pieces shared by the global AI Chat page and the deal
// QA tab: the scope header, the empty-state suggestions, and the message
// bubble with citations.

import Link from "next/link";
import { BookOpen, Sparkles } from "lucide-react";
import { LoadingState } from "@/components/shared/loading-state";
import type { Citation, Deal, Meeting } from "@/types";
import { citationHref, type Scope } from "./types";

// The minimal message shape Bubble needs — both pages' ChatMsg types satisfy
// it structurally (their scope unions differ, so the bubble takes the deal id
// for citation links explicitly).
export interface BubbleMsg {
  id: string;
  role: "user" | "ai";
  text: string;
  citations?: Citation[];
  pending?: boolean;
  groundingScore?: number;
}

export function ConversationHeader({
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
                : scope.kind === "meeting"
                  ? activeMeeting?.title ?? "Meeting"
                  : `${scope.meetingIds.length} meetings`}
            </span>
            {scope.kind === "deal" ? (
              <span>· deal-wide context</span>
            ) : scope.kind === "meeting" ? (
              <span>· single meeting</span>
            ) : (
              <span>· {scope.meetingIds.length} selected meetings</span>
            )}
          </>
        ) : (
          <span>Select a deal to begin.</span>
        )}
      </span>
    </div>
  );
}

export function EmptyChat({
  dealName,
  suggestions,
  onPick,
}: {
  dealName: string;
  suggestions: string[];
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
        {suggestions.map((s) => (
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

export function Bubble({ msg, dealId }: { msg: BubbleMsg; dealId: string }) {
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
