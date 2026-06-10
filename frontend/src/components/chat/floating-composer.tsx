"use client";

// The fixed bottom composer of the global AI Chat: scope chip, input, send
// button, and the first-message suggestion pills.

import { ArrowRight, Briefcase, Mic, Send, Sparkles } from "lucide-react";
import type { Deal, Meeting } from "@/types";
import type { Scope } from "./types";

export function FloatingComposer({
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
