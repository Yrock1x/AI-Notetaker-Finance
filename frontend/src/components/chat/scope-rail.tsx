"use client";

// Left rail of the global AI Chat: deal selector with the active deal's
// meetings cascading underneath, plus a text filter over both.

import { useMemo, useState } from "react";
import {
  Briefcase,
  ChevronDown,
  ChevronRight,
  Mic,
  Search,
} from "lucide-react";
import type { Deal, Meeting } from "@/types";
import type { Scope } from "./types";

export function ScopeRail({
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
