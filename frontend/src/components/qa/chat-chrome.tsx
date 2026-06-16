"use client";

// QA-tab-specific chrome: the deal/meeting scope rail, conversation header,
// and floating composer. The message bubble + empty state are shared with
// the global chat page (components/chat/conversation.tsx).

import {
  ArrowRight,
  Check,
  Mic,
  MoreHorizontal,
  Plus,
  Search,
  Send,
  Sparkles,
} from "lucide-react";
import { PillButton } from "@/components/workspace/primitives";
import type { Citation, Meeting } from "@/types";

// Scope is deal-relative here (the page already lives under /deals/[dealId]),
// unlike the global chat page whose scope carries the deal id.
//   deal      → the whole deal (all meetings & documents)
//   meeting   → exactly one meeting (uses the optimized single-meeting endpoint)
//   meetings  → a selected subset (2+) of meetings
export type Scope =
  | { kind: "deal" }
  | { kind: "meeting"; meetingId: string }
  | { kind: "meetings"; meetingIds: string[] };

// The selected meeting ids implied by a scope ([] for deal-wide).
export function selectedMeetingIds(scope: Scope): string[] {
  if (scope.kind === "meeting") return [scope.meetingId];
  if (scope.kind === "meetings") return scope.meetingIds;
  return [];
}

// Collapse a selection set back to the narrowest scope: none → deal, one →
// single-meeting (optimized path), many → subset.
export function scopeFromMeetingIds(ids: string[]): Scope {
  if (ids.length === 0) return { kind: "deal" };
  if (ids.length === 1) return { kind: "meeting", meetingId: ids[0] };
  return { kind: "meetings", meetingIds: ids };
}

export interface QaChatMsg {
  id: string;
  role: "user" | "ai";
  text: string;
  citations?: Citation[];
  pending?: boolean;
  scope: Scope;
  groundingScore?: number;
}

export function ScopeRail({
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
  const selected = selectedMeetingIds(scope);
  const selectedSet = new Set(selected);
  const toggle = (id: string) => {
    const next = selectedSet.has(id)
      ? selected.filter((x) => x !== id)
      : [...selected, id];
    onScope(scopeFromMeetingIds(next));
  };
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
            All meetings & documents
          </div>
          <div className="text-[11px]" style={{ color: "var(--ws-muted)" }}>
            Deal-wide context · {dealName}
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
      {selected.length > 0 && (
        <div
          className="px-3.5 py-1.5 flex items-center gap-2 text-[11px]"
          style={{
            borderBottom: "1px solid var(--ws-border)",
            background: "var(--ws-ai-tint)",
            color: "var(--ws-ai-ink)",
            fontWeight: 600,
          }}
        >
          <span>
            {selected.length} meeting{selected.length === 1 ? "" : "s"} selected
          </span>
          <div className="flex-1" />
          <button
            type="button"
            onClick={() => onScope({ kind: "deal" })}
            style={{ color: "var(--ws-ai-ink)", textDecoration: "underline" }}
          >
            Clear
          </button>
        </div>
      )}
      <div className="flex-1 overflow-y-auto">
        {meetings.length === 0 ? (
          <div className="px-3.5 py-3 text-[11.5px]" style={{ color: "var(--ws-faint)" }}>
            No meetings to scope to.
          </div>
        ) : (
          meetings.map((m, i) => {
            const active = selectedSet.has(m.id);
            const d = m.meeting_date
              ? new Date(m.meeting_date)
              : new Date(m.created_at);
            return (
              <button
                key={m.id}
                type="button"
                onClick={() => toggle(m.id)}
                className="w-full grid grid-cols-[auto_1fr] gap-2.5 items-start px-3.5 py-2 text-left cursor-pointer"
                style={{
                  background: active ? "var(--ws-ai-tint)" : "transparent",
                  borderLeft: `2px solid ${active ? "var(--ws-ai-ink)" : "transparent"}`,
                  borderTop: i > 0 ? "1px solid var(--ws-border)" : undefined,
                }}
              >
                <span
                  className="w-3.5 h-3.5 mt-0.5 shrink-0 grid place-items-center rounded-[3px]"
                  style={{
                    border: `1.5px solid ${active ? "var(--ws-ai-ink)" : "var(--ws-border-strong)"}`,
                    background: active ? "var(--ws-ai-ink)" : "transparent",
                  }}
                >
                  {active && <Check className="w-2.5 h-2.5" style={{ color: "#fff" }} />}
                </span>
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

export function ConversationHeader({
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
          {scope.kind === "deal"
            ? dealName
            : scope.kind === "meeting"
              ? (scopedMeeting?.title ?? "Meeting")
              : `${scope.meetingIds.length} meetings`}
        </span>
        {scope.kind === "deal" ? (
          <span>· deal-wide context</span>
        ) : scope.kind === "meeting" ? (
          <span>· single meeting</span>
        ) : (
          <span>· {scope.meetingIds.length} selected meetings</span>
        )}
      </span>
      <div className="flex-1" />
      <PillButton>
        <MoreHorizontal className="w-3 h-3" />
      </PillButton>
    </div>
  );
}

export function FloatingComposer({
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
            title={
              scope.kind === "deal"
                ? dealName
                : scope.kind === "meeting"
                  ? scopedMeeting?.title
                  : `${scope.meetingIds.length} meetings`
            }
          >
            {scope.kind === "deal" ? (
              <>
                <Sparkles className="w-2.5 h-2.5" /> Deal-wide
              </>
            ) : (
              <>
                <Mic className="w-2.5 h-2.5" />
                <span className="max-w-[120px] truncate">
                  {scope.kind === "meeting"
                    ? (scopedMeeting?.title ?? "Meeting")
                    : `${scope.meetingIds.length} meetings`}
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
                : scope.kind === "meeting"
                  ? `Ask about this meeting…`
                  : `Ask about these ${scope.meetingIds.length} meetings…`
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
