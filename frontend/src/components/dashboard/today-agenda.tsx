"use client";

import Link from "next/link";
import { ArrowRight, ExternalLink, Mic } from "lucide-react";
import { useScribeTheme } from "@/components/cogniscribe/theme-provider";
import { useTodayMeetings, type TodayMeeting } from "@/hooks/use-today-meetings";
import { Skeleton } from "@/components/ui/skeleton";

function formatTime(iso?: string): string {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  });
}

function meetingHref(m: TodayMeeting): string | null {
  if (!m.deal_id) return null;
  return `/deals/${m.deal_id}/meetings/${m.id}`;
}

export function TodayAgenda() {
  const { isDark } = useScribeTheme();
  const { meetings, isLoading } = useTodayMeetings();

  const todayLabel = new Date().toLocaleDateString(undefined, {
    weekday: "long",
    month: "short",
    day: "numeric",
  });

  // Collapse entirely on a clear day — the dashboard's job is the ask box and
  // the deal switcher; today's calls only earn screen space when they exist.
  if (!isLoading && meetings.length === 0) return null;

  return (
    <section
      className={`rounded-2xl border p-6 ${
        isDark
          ? "bg-[#121212] border-white/10"
          : "bg-white border-black/[0.06]"
      }`}
    >
      <div className="flex items-end justify-between mb-5">
        <div className="flex items-center gap-3">
          <span className="inline-block h-5 w-1 rounded-full bg-gradient-to-b from-emerald-400 to-emerald-600" />
          <div className="flex flex-col gap-0.5">
            <span
              className={`text-[10px] font-medium tracking-[0.22em] uppercase ${
                isDark ? "text-emerald-300/80" : "text-emerald-600"
              }`}
            >
              Today
            </span>
            <h2 className="text-[20px] sm:text-[22px] tracking-[-0.01em] font-medium">
              {todayLabel}
            </h2>
          </div>
        </div>
        <Link
          href="/calendar"
          className={`group flex items-center gap-1.5 text-[12.5px] font-medium ${
            isDark ? "text-white/65 hover:text-white" : "text-black/65 hover:text-black"
          }`}
        >
          View calendar
          <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" />
        </Link>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      ) : meetings.length === 0 ? (
        <p className={`text-sm ${isDark ? "text-white/40" : "text-black/40"}`}>
          Nothing on your schedule today.
        </p>
      ) : (
        <ul className="space-y-1.5">
          {meetings.map((m) => {
            const href = meetingHref(m);
            const Wrapper = href
              ? ({ children }: { children: React.ReactNode }) => (
                  <Link href={href} className="block">
                    {children}
                  </Link>
                )
              : ({ children }: { children: React.ReactNode }) => (
                  <div>{children}</div>
                );
            return (
              <li key={m.id}>
                <Wrapper>
                  <div
                    className={`group flex items-center gap-3 rounded-xl px-3 py-2.5 transition-all ${
                      m.isLive
                        ? isDark
                          ? "bg-rose-500/[0.07] ring-1 ring-rose-400/20"
                          : "bg-rose-50 ring-1 ring-rose-200"
                        : isDark
                          ? "hover:bg-white/[0.04]"
                          : "hover:bg-black/[0.03]"
                    }`}
                  >
                    <span
                      className={`inline-flex items-center justify-center h-8 w-16 shrink-0 rounded-lg font-data tabular-nums text-[11.5px] font-semibold ${
                        m.isLive
                          ? "bg-rose-500 text-white"
                          : isDark
                            ? "bg-emerald-500/15 text-emerald-300"
                            : "bg-emerald-50 text-emerald-700"
                      }`}
                    >
                      {formatTime(m.meeting_date)}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{m.title}</p>
                      <p
                        className={`truncate text-[11.5px] ${
                          isDark ? "text-white/45" : "text-black/45"
                        }`}
                      >
                        {m.deal_name || "Unassigned"}
                      </p>
                    </div>
                    {m.isLive && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-rose-500/15 px-2 py-0.5 text-[10px] font-semibold text-rose-500">
                        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-rose-500" />
                        LIVE
                        <Mic className="h-2.5 w-2.5" />
                      </span>
                    )}
                    {m.joinUrl && !m.isLive && (
                      <a
                        href={m.joinUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[10.5px] font-medium transition-colors ${
                          isDark
                            ? "bg-indigo-500/10 text-indigo-300 hover:bg-indigo-500/20"
                            : "bg-indigo-50 text-indigo-700 hover:bg-indigo-100"
                        }`}
                      >
                        Join <ExternalLink className="h-2.5 w-2.5" />
                      </a>
                    )}
                  </div>
                </Wrapper>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
